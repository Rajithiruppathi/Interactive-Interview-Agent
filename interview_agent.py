import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interview_memory.json")

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
    "After each candidate response, write a private technical evaluation in 'inner_evaluation', "
    "then craft your next question in 'interview_question'. "
    "Set 'session_state' to 'CONCLUDE' only when the candidate says goodbye or explicitly ends the session; "
    "otherwise always set it to 'CONTINUE'."
)


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all top-level keys exist when loading an older schema
            data.setdefault("user_profile", {"target_roles": [], "tech_stack": []})
            data.setdefault("performance_logs", [])
            data.setdefault("improvement_tracker", {})
            return data
        except (json.JSONDecodeError, IOError):
            pass  # Fall through and create a fresh file

    return {
        "user_profile": {"target_roles": [], "tech_stack": []},
        "performance_logs": [],
        "improvement_tracker": {},
    }


def save_memory(memory: dict) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[Warning: could not save memory: {e}]", file=sys.stderr)


def log_exchange(
    memory: dict,
    *,
    company: str,
    question: str,
    answer: str,
    latency_seconds: float,
    input_tokens: int,
    output_tokens: int,
    struggled: bool,
    inner_evaluation: str = "",
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "company_scraped": company,
        "question": question,
        "user_answer": answer,
        "latency_seconds": round(latency_seconds, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "struggled": struggled,
        "inner_evaluation": inner_evaluation,
    }
    memory["performance_logs"].append(entry)

    if struggled and question:
        # Use the first 80 chars of the question as the topic key
        topic = question[:80].strip()
        memory["improvement_tracker"][topic] = (
            memory["improvement_tracker"].get(topic, 0) + 1
        )


def detect_struggle(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in STRUGGLE_PHRASES)


def _build_welcome_back_prompt(memory: dict) -> str:
    logs = memory["performance_logs"]
    last = logs[-1]
    company = last.get("company_scraped") or "unknown"
    total = len(logs)
    roles = memory["user_profile"].get("target_roles", [])
    struggled_topics = list(memory.get("improvement_tracker", {}).keys())

    ctx_parts = [f"Past session data: {total} logged Q&A exchange(s)."]
    if company and company != "unknown":
        ctx_parts.append(f"Last company discussed: {company}.")
    if roles:
        ctx_parts.append(f"Candidate's target roles: {', '.join(roles)}.")
    if struggled_topics:
        ctx_parts.append(
            f"Topics the candidate struggled with (to revisit): "
            f"{', '.join(struggled_topics[:3])}."
        )
    context_block = " ".join(ctx_parts)

    return (
        f"[Memory context — do not read this aloud verbatim: {context_block}] "
        "Welcome the candidate back warmly. Reference their previous session specifically "
        "(e.g. mention the last company or topic they worked on). "
        "Then ask if they'd like to pick up where they left off or target a new role/company today."
    )


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

def get_client():
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


def _token_counts(response) -> tuple[int, int]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    return (
        getattr(meta, "prompt_token_count", 0) or 0,
        getattr(meta, "candidates_token_count", 0) or 0,
    )


def _parse_response(text: str) -> InterviewerResponse | None:
    try:
        return InterviewerResponse.model_validate_json(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main interview loop
# ---------------------------------------------------------------------------

def run_interview():
    memory = load_memory()
    has_history = bool(memory["performance_logs"])
    client = get_client()

    try:
        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[scrape_company_website],
                response_mime_type="application/json",
                response_schema=InterviewerResponse,
            ),
        )
    except APIError as e:
        print(f"API Error while starting session: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error while starting session: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("  Day 4 Interview Agent (Structured Output + Hidden Eval)")
    print("  Paste a company URL to tailor questions, or type 'exit'/'quit'.")
    print("=" * 60)
    print()

    # Opening greeting — personalised when prior history exists
    try:
        opening_prompt = (
            _build_welcome_back_prompt(memory)
            if has_history
            else (
                "Greet the candidate warmly, then ask what specific job role "
                "and company they are interviewing for today. Mention they can paste "
                "the company's website URL so you can tailor your questions."
            )
        )
        t0 = time.perf_counter()
        opening = chat.send_message(opening_prompt)
        opening = _resolve_tool_calls(chat, opening)
        latency = time.perf_counter() - t0

        parsed_opening = _parse_response(opening.text)
        opening_text = parsed_opening.interview_question if parsed_opening else opening.text
        print(f"Interviewer: {opening_text}\n")
        print(f"[Latency: {latency:.2f}s]\n")
    except APIError as e:
        print(f"API Error during greeting: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during greeting: {e}", file=sys.stderr)
        sys.exit(1)

    current_company = "unknown"
    last_question = opening_text  # Seed: first thing the agent said

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            save_memory(memory)
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("\nInterviewer: Thank you for your time. Good luck with your interview!")
            save_memory(memory)
            break

        # Track company URL if the user pastes one
        for word in user_input.split():
            if word.startswith("http://") or word.startswith("https://"):
                current_company = word
                break

        struggled = detect_struggle(user_input)

        try:
            t0 = time.perf_counter()
            response = chat.send_message(user_input)
            response = _resolve_tool_calls(chat, response)
            latency = time.perf_counter() - t0

            in_tok, out_tok = _token_counts(response)

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
                memory,
                company=current_company,
                question=last_question,
                answer=user_input,
                latency_seconds=latency,
                input_tokens=in_tok,
                output_tokens=out_tok,
                struggled=struggled,
                inner_evaluation=inner_eval,
            )
            save_memory(memory)

            print(f"\nInterviewer: {agent_reply}\n")
            print(f"[Latency: {latency:.2f}s | Tokens in: {in_tok} | out: {out_tok}]")
            if struggled:
                print("[Memory: flagged as a struggle topic for future review]")
            print()

            last_question = agent_reply

            if session_concluded:
                save_memory(memory)
                break

        except APIError as e:
            print(f"\nAPI Error: {e}", file=sys.stderr)
            save_memory(memory)
            sys.exit(1)
        except Exception as e:
            print(f"\nUnexpected error: {e}", file=sys.stderr)
            save_memory(memory)
            sys.exit(1)


if __name__ == "__main__":
    run_interview()
