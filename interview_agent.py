import os
import re
import sys
import time
import requests
import psycopg2
import psycopg2.extras
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from langfuse import get_client

load_dotenv()

# Initialize Langfuse client and setup OTel instrumentation for google-genai SDK
langfuse_client = get_client()
GoogleGenAIInstrumentor().instrument()

STRUGGLE_PHRASES = {
    "i don't remember", "i dont remember", "i'm not sure", "im not sure",
    "i don't know", "i dont know", "not familiar", "i forget", "i forgot",
    "no idea", "i can't recall", "i cannot recall", "i'm unsure", "im unsure",
    "i have no idea", "i'm drawing a blank", "i am not sure",
}


class InterviewerResponse(BaseModel):
    inner_evaluation: str = Field(
        description=(
            "Your private technical analysis of the candidate's last response. "
            "Highlight structural gaps, misconceptions, or genuine strengths. "
            "This is never shown to the candidate."
        )
    )
    interview_question: str = Field(
        description=(
            "The single, highly tailored conversational question to present to the candidate next. "
            "This is the only text the candidate sees."
        )
    )
    session_state: str = Field(
        description='Must be exactly "CONTINUE" or "CONCLUDE". Set to "CONCLUDE" only when the candidate explicitly ends the session.'
    )


SYSTEM_INSTRUCTION = (
    "You are an expert technical interviewer conducting a structured session. "
    "Ask role-specific questions one at a time and keep your tone professional. "
    "You have access to a web-scraping tool. If the user provides a company URL, "
    "scrape the website, analyze the company's engineering culture, and tailor your questions accordingly. "
    "\n\n"
    "CRITICAL: Every reply you send — including your opening greeting — MUST be a single valid JSON object "
    "with exactly these three keys. No markdown, no code fences, no prose — raw JSON only:\n"
    "  inner_evaluation  — Your private technical analysis of the candidate's last response. "
    "Note structural gaps, misconceptions, or genuine strengths. Never reveal this to the candidate.\n"
    "  interview_question — The single tailored question (or greeting) to present to the candidate. "
    "This is the only content the candidate sees.\n"
    "  session_state — The string 'CONTINUE' or 'CONCLUDE'. "
    "Use 'CONCLUDE' only when the candidate explicitly ends the session; otherwise always 'CONTINUE'.\n\n"
    'Example: {"inner_evaluation": "Candidate demonstrated solid feature engineering but skipped class-imbalance handling.", '
    '"interview_question": "How would you handle severe class imbalance in your fraud dataset?", '
    '"session_state": "CONTINUE"}'
)


# ---------------------------------------------------------------------------
# Observability & Alerting
# ---------------------------------------------------------------------------

def alert_internal_team(error_type: str, exception_details: str) -> None:
    print(
        f"🚨 [INTERNAL SYSTEM ALERT] Critical Infrastructure Failure Encountered: "
        f"{error_type} | Details: {exception_details}",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise psycopg2.OperationalError("DATABASE_URL environment variable not set.")
    return psycopg2.connect(db_url)


def _init_db() -> bool:
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS candidate_sessions (
                    session_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    target_roles TEXT[],
                    tech_stack TEXT[]
                );
                CREATE TABLE IF NOT EXISTS conversation_logs (
                    log_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    question TEXT,
                    user_answer TEXT,
                    inner_evaluation TEXT,
                    struggled BOOLEAN DEFAULT FALSE,
                    latency_seconds NUMERIC(6,3)
                );
            """)
        conn.commit()
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        alert_internal_team("DB Initialization Failure", str(e))
        print(
            "⚠️ [DATABASE FALLBACK] Database offline. Using local dictionary state tracking instead.",
            file=sys.stderr,
        )
        return False


def _has_prior_history() -> bool:
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conversation_logs")
            count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except psycopg2.OperationalError:
        return False


def _build_welcome_back_prompt() -> str:
    default = (
        "Greet the candidate warmly, then ask what specific job role "
        "and company they are interviewing for today. Mention they can paste "
        "the company's website URL so you can tailor your questions."
    )
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) FROM conversation_logs")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT question, struggled FROM conversation_logs ORDER BY timestamp DESC LIMIT 3"
            )
            recent = cur.fetchall()
            cur.execute(
                "SELECT target_roles FROM candidate_sessions ORDER BY timestamp DESC LIMIT 1"
            )
            session_row = cur.fetchone()
        conn.close()

        roles = session_row["target_roles"] if session_row and session_row["target_roles"] else []
        struggled_topics = [r["question"][:60] for r in recent if r["struggled"]]

        ctx_parts = [f"Prior session data: {total} logged exchange(s)."]
        if roles:
            ctx_parts.append(f"Candidate's target roles: {', '.join(roles)}.")
        if struggled_topics:
            ctx_parts.append(f"Topics to revisit: {'; '.join(struggled_topics[:2])}.")
        context_block = " ".join(ctx_parts)

        return (
            f"[Memory context — do not read this aloud verbatim: {context_block}] "
            "Welcome the candidate back warmly. Reference their previous session. "
            "Ask if they'd like to continue or target a new role/company today."
        )
    except psycopg2.OperationalError:
        return default


def log_exchange(
    *,
    question: str,
    user_answer: str,
    inner_evaluation: str,
    struggled: bool,
    latency_seconds: float,
    fallback_log: list,
) -> None:
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_logs
                    (question, user_answer, inner_evaluation, struggled, latency_seconds)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (question, user_answer, inner_evaluation, struggled, round(latency_seconds, 3)),
            )
        conn.commit()
        conn.close()
    except psycopg2.OperationalError as e:
        alert_internal_team("Log Exchange DB Write Failure", str(e))
        print(
            "⚠️ [DATABASE FALLBACK] Database offline. Using local dictionary state tracking instead.",
            file=sys.stderr,
        )
        fallback_log.append({
            "question": question,
            "user_answer": user_answer,
            "inner_evaluation": inner_evaluation,
            "struggled": struggled,
            "latency_seconds": round(latency_seconds, 3),
        })


# ---------------------------------------------------------------------------
# Struggle detection
# ---------------------------------------------------------------------------

def detect_struggle(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in STRUGGLE_PHRASES)


# ---------------------------------------------------------------------------
# Gemini tool
# ---------------------------------------------------------------------------

def scrape_company_website(url: str) -> str:
    """Fetches a company's website and extracts its main paragraph text.

    Use this to learn what a company does so interview questions can be
    tailored to its business and engineering culture.

    Args:
        url: The full URL of the company website to scrape.

    Returns:
        The cleaned paragraph text from the page, or a message describing
        why the page could not be read.
    """
    try:
        response = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Error: could not fetch '{url}' ({e})."

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        text = " ".join(text.split())
    except Exception as e:
        return f"Error: could not parse content from '{url}' ({e})."

    if not text:
        return f"No readable paragraph text was found at '{url}'."

    return text[:4000]


# ---------------------------------------------------------------------------
# Gemini client + tool-call loop
# ---------------------------------------------------------------------------

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.", file=sys.stderr)
        print("Please set it or create a .env file.", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def _resolve_tool_calls(chat, response):
    """Drives the tool-call loop until the model returns a plain text reply."""
    while response.function_calls:
        tool_parts = []
        for fn_call in response.function_calls:
            if fn_call.name == "scrape_company_website":
                print("\n[Agent is scraping the website...]\n")
                result = scrape_company_website(**fn_call.args)
            else:
                result = f"Unknown tool requested: {fn_call.name}"

            tool_parts.append(
                types.Part.from_function_response(
                    name=fn_call.name,
                    response={"result": result},
                )
            )
        response = chat.send_message(tool_parts)
    return response


def _parse_response(text: str) -> InterviewerResponse | None:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip())
        return InterviewerResponse.model_validate_json(cleaned.strip())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main interview loop
# ---------------------------------------------------------------------------

def run_interview():
    fallback_log: list = []
    db_online = _init_db()
    has_history = _has_prior_history() if db_online else False

    client = get_gemini_client()

    try:
        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[scrape_company_website],
            ),
        )
    except APIError as e:
        alert_internal_team("Gemini Chat Initialization Failure", str(e))
        sys.exit(1)
    except Exception as e:
        alert_internal_team("Unexpected Chat Initialization Failure", str(e))
        sys.exit(1)

    print("=" * 60)
    print("  Day 5 Interview Agent (Enterprise Migration + Observability)")
    print("  Paste a company URL to tailor questions, or type 'exit'/'quit'.")
    print("=" * 60)
    print()

    # Opening greeting — personalised when prior history exists in DB
    try:
        opening_prompt = (
            _build_welcome_back_prompt()
            if has_history
            else (
                "Greet the candidate warmly, then ask what specific job role "
                "and company they are interviewing for today. Mention they can paste "
                "the company's website URL so you can tailor your questions."
            )
        )
        opening = chat.send_message(opening_prompt)
        opening = _resolve_tool_calls(chat, opening)

        parsed_opening = _parse_response(opening.text)
        opening_text = parsed_opening.interview_question if parsed_opening else opening.text
        print(f"Interviewer: {opening_text}\n")
    except APIError as e:
        alert_internal_team("Gemini API Error During Greeting", str(e))
        sys.exit(1)
    except Exception as e:
        alert_internal_team("Unexpected Error During Greeting", str(e))
        sys.exit(1)

    last_question = opening_text

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("\nInterviewer: Thank you for your time. Good luck with your interview!")
            break

        struggled = detect_struggle(user_input)

        try:
            t0 = time.perf_counter()
            response = chat.send_message(user_input)
            response = _resolve_tool_calls(chat, response)
            latency = time.perf_counter() - t0

            parsed = _parse_response(response.text)
            if parsed:
                agent_reply = parsed.interview_question
                inner_eval = parsed.inner_evaluation
                session_concluded = parsed.session_state == "CONCLUDE"
            else:
                agent_reply = response.text
                inner_eval = ""
                session_concluded = False

            log_exchange(
                question=last_question,
                user_answer=user_input,
                inner_evaluation=inner_eval,
                struggled=struggled,
                latency_seconds=latency,
                fallback_log=fallback_log,
            )

            print(f"\nInterviewer: {agent_reply}\n")

            last_question = agent_reply

            if session_concluded:
                break

        except APIError as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                alert_internal_team("API Rate Limit (429 Resource Exhausted)", err_str)
            else:
                alert_internal_team("Gemini API Error", err_str)
            sys.exit(1)
        except Exception as e:
            alert_internal_team("Unexpected Runtime Error", str(e))
            sys.exit(1)


if __name__ == "__main__":
    run_interview()
