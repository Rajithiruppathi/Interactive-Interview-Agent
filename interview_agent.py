import os
import sys
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()

SYSTEM_INSTRUCTION = (
    "You are an expert technical interviewer. "
    "Ask role-specific questions one at a time, wait for the user's response, "
    "and keep your tone professional. "
    "You now have access to a web-scraping tool. If the user provides a company URL, "
    "use your tool to scrape the website, analyze what the company does, deduce their "
    "engineering/business culture, and use that context to tailor your interview questions."
)


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


def get_client():
    """
    Initializes and returns the Gemini client.
    Checks GEMINI_API_KEY first, then GOOGLE_API_KEY as a fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.", file=sys.stderr)
        print("Please set the GEMINI_API_KEY environment variable or create a .env file.", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def _resolve_tool_calls(chat, response):
    """Drives the tool-call loop until the model returns a plain text reply.

    When Gemini decides to call a tool it returns function_call parts instead
    of text.  We execute each requested function locally, send all results back
    in a single turn, and repeat until the model is done calling tools.
    """
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


def run_interview():
    client = get_client()

    try:
        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[scrape_company_website],
            ),
        )
    except APIError as e:
        print(f"API Error while starting session: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error while starting session: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("  Day 2 Interactive Interview Agent (with Web-Scraping Tool)")
    print("  Paste a company URL to give the agent context, or type 'exit'/'quit' to end.")
    print("=" * 60)
    print()

    # Opening greeting — agent asks for role and company
    try:
        opening = chat.send_message(
            "Greet the candidate warmly, then ask them what specific job role "
            "and company they are interviewing for today. Mention they can paste "
            "the company's website URL so you can tailor your questions."
        )
        opening = _resolve_tool_calls(chat, opening)
        print(f"Interviewer: {opening.text}\n")
    except APIError as e:
        print(f"API Error during greeting: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during greeting: {e}", file=sys.stderr)
        sys.exit(1)

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

        try:
            response = chat.send_message(user_input)
            response = _resolve_tool_calls(chat, response)
            print(f"\nInterviewer: {response.text}\n")
        except APIError as e:
            print(f"\nAPI Error: {e}", file=sys.stderr)
            print("The session has ended due to an API error.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nUnexpected error: {e}", file=sys.stderr)
            print("The session has ended due to an unexpected error.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    run_interview()
