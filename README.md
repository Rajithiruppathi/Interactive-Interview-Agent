# Interactive Interview Agent

An AI-powered technical interview coach built incrementally across a 5-day Kaggle AI Agents course. The agent conducts realistic mock interviews, tailors questions to a specific company by scraping its website, privately evaluates your answers, and persists all session data to a cloud PostgreSQL database with full observability via Langfuse.

---

## Features

- **Conversational interview loop** — Gemini 2.5 Flash drives the session, asking one focused technical question at a time
- **Company-aware questions** — paste any company URL and the agent scrapes it to tailor questions to their engineering culture
- **Hidden evaluator** — every response is silently scored in `inner_evaluation` (never shown to you); only the next question appears in the terminal
- **Structured output** — responses are parsed as a typed `InterviewerResponse` Pydantic schema (`inner_evaluation`, `interview_question`, `session_state`)
- **Auto-conclude** — the session closes automatically when the model signals `session_state: CONCLUDE`
- **Struggle detection** — phrases like "I'm not sure" or "I don't know" flag the exchange for targeted follow-up in future sessions
- **PostgreSQL persistence** — all Q&A exchanges, inner evaluations, latency, and struggle flags are written to Neon cloud DB
- **Langfuse observability** — OpenTelemetry auto-instrumentation captures token counts, latency, and full traces in the Langfuse dashboard
- **Resilient fallback** — if the database is offline the session continues writing to an in-memory log, never crashing
- **Enterprise alert pipeline** — `alert_internal_team()` fires on any API or DB failure, including 429 rate-limit detection

---

## Day-by-Day Build Log

| Day | Branch | What was built |
|-----|--------|---------------|
| 1 | `day1-interview-agent` | Baseline Gemini chat loop with system instruction |
| 2 | `day2-interview-agent` | `scrape_company_website` tool; agent tailors questions from a URL |
| 3 | `day3-interview-agent` | Persistent JSON memory — struggle tracking, welcome-back prompt, token/latency logging |
| 4 | `day4-interview-agent` | `InterviewerResponse` Pydantic schema, hidden `inner_evaluation`, auto-CONCLUDE exit |
| 5 | `day5-interview-agent` | PostgreSQL migration (Neon), Langfuse OTel instrumentation, DB fallback, alert pipeline |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.5 Flash (`google-genai`) |
| Schema validation | Pydantic v2 |
| Web scraping | BeautifulSoup4 + Requests |
| Database | PostgreSQL on Neon (`psycopg2-binary`) |
| Observability | Langfuse + OpenInference OTel instrumentation |
| Config | python-dotenv |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/Rajithiruppathi/Interactive-Interview-Agent.git
cd Interactive-Interview-Agent
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# Gemini API
GEMINI_API_KEY=your_gemini_api_key

# Neon PostgreSQL (Day 5+)
DATABASE_URL=postgresql://user:password@host/dbname

# Langfuse Observability (Day 5+)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

> **Note:** `DATABASE_URL` and Langfuse keys are only required for Day 5. If omitted, the agent falls back to in-memory state tracking with a warning.

### 3. Run

```bash
python interview_agent.py
```

---

## Usage

```
============================================================
  Day 5 Interview Agent (Enterprise Migration + Observability)
  Paste a company URL to tailor questions, or type 'exit'/'quit'.
============================================================

Interviewer: Welcome! What role and company are you targeting today?
             Feel free to paste the company URL so I can tailor my questions.

You: Data Scientist at Stripe — https://stripe.com

[Agent is scraping the website...]

Interviewer: Stripe operates at massive payment-processing scale with a
             strong emphasis on fraud prevention. Walk me through how you
             would design a real-time fraud detection model. What features
             would you engineer and why?

You: I would use velocity features, device fingerprinting, and MCC codes...
```

- Paste a company URL anywhere in your message to trigger website scraping
- Type `exit` or `quit` to end the session manually
- Say goodbye naturally (e.g. "That's all for today") and the agent concludes on its own

---

## Database Schema

Two tables are created automatically on first run:

```sql
CREATE TABLE IF NOT EXISTS candidate_sessions (
    session_id  SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    target_roles TEXT[],
    tech_stack   TEXT[]
);

CREATE TABLE IF NOT EXISTS conversation_logs (
    log_id           SERIAL PRIMARY KEY,
    timestamp        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    question         TEXT,
    user_answer      TEXT,
    inner_evaluation TEXT,   -- hidden agent critique, never shown to candidate
    struggled        BOOLEAN DEFAULT FALSE,
    latency_seconds  NUMERIC(6,3)
);
```

---

## Project Structure

```
├── interview_agent.py   # Main agent — all logic lives here
├── requirements.txt     # Python dependencies
├── .gitignore           # Excludes .env, __pycache__, interview_memory.json
└── AGENTS.md            # Course milestone tracker
```

---

## Observability

With valid Langfuse credentials every session is automatically traced:

- Full prompt/response pairs per turn
- Token usage (input + output)
- Latency per API call
- Tool call spans (website scraping)

View traces at [cloud.langfuse.com](https://cloud.langfuse.com) after running a session.
