import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()

SYSTEM_INSTRUCTION = (
    "You are an expert technical interviewer. "
    "Ask role-specific questions one at a time, wait for the user's response, "
    "and keep your tone professional."
)

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


def run_interview():
    client = get_client()

    try:
        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )
    except APIError as e:
        print(f"API Error while starting session: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error while starting session: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("  Day 1 Interactive Interview Agent")
    print("  Type 'exit' or 'quit' to end the session.")
    print("=" * 60)
    print()

    # Opening greeting — agent asks for role and company
    try:
        opening = chat.send_message(
            "Greet the candidate warmly, then ask them what specific job role "
            "and company they are interviewing for today."
        )
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
