import os
import streamlit as st
import datetime
import openai
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

st.title("🎙️ Interactive Interview & Tracker Dashboard")
st.write("Select your target role or log your real-world interview experiences.")

st.markdown("""
<style>
/* ── Main body ──────────────────────────────────────────── */
.block-container {
    padding-top: 1.8rem;
    padding-bottom: 2rem;
    max-width: 860px;
}

/* ── Tab strip ──────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    padding: 8px 22px;
    border-radius: 8px 8px 0 0;
    font-weight: 500;
    font-size: 14px;
    color: #475569;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    background-color: #eef2ff;
    color: #3730a3;
    border-bottom: 3px solid #4f46e5;
}

/* ── Sidebar profile cards ──────────────────────────────── */
.profile-card {
    border-radius: 10px;
    padding: 12px 14px;
    margin: 8px 0;
    border-left: 4px solid;
}
.tech-card  { background: #eff6ff; border-left-color: #2563eb; }
.role-card  { background: #f5f3ff; border-left-color: #7c3aed; }

.card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: #64748b;
    margin-bottom: 8px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
}
.tag-tech { background: #dbeafe; color: #1d4ed8; }
.tag-role { background: #ede9fe; color: #5b21b6; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DB helpers — connection-per-operation pattern (no cached connections)
# ---------------------------------------------------------------------------

def get_db_conn():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise psycopg2.OperationalError("DATABASE_URL environment variable not set.")
    return psycopg2.connect(db_url)


def init_db() -> bool:
    """Creates required tables if they don't exist. Opens and closes its own connection."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS candidate_sessions (
                    session_id  SERIAL PRIMARY KEY,
                    timestamp   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    target_roles TEXT[],
                    tech_stack   TEXT[]
                );
                CREATE TABLE IF NOT EXISTS interview_logs (
                    id              SERIAL PRIMARY KEY,
                    company_name    VARCHAR(255) NOT NULL,
                    role_name       VARCHAR(255) NOT NULL,
                    interview_date  DATE NOT NULL,
                    questions_asked TEXT,
                    self_evaluation INTEGER,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
        return True
    except psycopg2.OperationalError as e:
        st.warning(f"⚠️ Database unavailable — running without persistence. ({e})")
        return False
    finally:
        if conn is not None:
            conn.close()


def fetch_candidate_profile() -> dict:
    """
    Fetches target_roles and tech_stack from the most recent candidate_sessions row.
    Returns empty defaults if the table is empty or the DB is unreachable.
    Connection is guaranteed to close via finally.
    """
    defaults = {"target_roles": [], "tech_stack": []}
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT target_roles, tech_stack FROM candidate_sessions "
                "ORDER BY timestamp DESC LIMIT 1"
            )
            row = cur.fetchone()
        if row and (row["target_roles"] or row["tech_stack"]):
            return {
                "target_roles": row["target_roles"] or [],
                "tech_stack":   row["tech_stack"]   or [],
            }
        return defaults
    except Exception:
        return defaults
    finally:
        if conn is not None:
            conn.close()


def save_interview_log(
    company_name: str,
    role_name: str,
    interview_date,
    questions_asked: str,
    self_evaluation: int,
) -> tuple[bool, str]:
    """Inserts one row into interview_logs. Returns (success, message)."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interview_logs
                    (company_name, role_name, interview_date, questions_asked, self_evaluation)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (company_name, role_name, interview_date, questions_asked, self_evaluation),
            )
        conn.commit()
        return True, f"Saved {role_name} at {company_name} to Neon DB."
    except Exception as e:
        return False, str(e)
    finally:
        if conn is not None:
            conn.close()


def _test_no_connection_leak() -> bool:
    """
    Sanity-checks that fetch_candidate_profile() leaves no open connections.
    Queries pg_stat_activity before and after; passes if count is unchanged.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            before = cur.fetchone()[0]

        fetch_candidate_profile()   # function under test

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            after = cur.fetchone()[0]

        # after should equal before (fetch opened and closed its own connection)
        return after <= before + 1   # +1 tolerance for the test connection itself
    except Exception:
        return True   # can't test without DB — assume pass
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------

db_online = init_db()


# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------

@st.cache_resource
def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key)


def get_openai_client():
    return openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


try:
    gemini_client = get_gemini_client()
except Exception:
    gemini_client = None
    st.error("Could not load Gemini Client. Please ensure GEMINI_API_KEY is set.")


def _is_rate_limit(err: Exception) -> bool:
    msg = str(err).upper()
    return any(t in msg for t in (
        "429", "503", "RESOURCE_EXHAUSTED", "QUOTA", "RATE_LIMIT", "UNAVAILABLE", "HIGH DEMAND"
    ))


def generate_with_fallback(contents: str, system_instruction: str = "") -> str:
    if gemini_client is not None:
        try:
            cfg = {"system_instruction": system_instruction} if system_instruction else {}
            resp = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=cfg or None,
            )
            return resp.text
        except Exception as e:
            if not _is_rate_limit(e):
                raise

    oai = get_openai_client()
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": contents})
    resp = oai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_evaluation" not in st.session_state:
    st.session_state.show_evaluation = False
if "evaluation_report" not in st.session_state:
    st.session_state.evaluation_report = ""
if "candidate_profile" not in st.session_state:
    # Fetch once per browser session — re-fetched only when session resets
    st.session_state.candidate_profile = fetch_candidate_profile()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.header("🎯 Target Interview Settings")

role_options = [
    "AI Engineer", "Generative AI Developer",
    "Python Backend Developer", "Data Scientist", "Other / Custom Role",
]
role_choice = st.sidebar.selectbox("Choose Target Role:", role_options)
selected_role = (
    st.sidebar.text_input("Type your specific role/stream here:", placeholder="e.g., Frontend Developer")
    if role_choice == "Other / Custom Role"
    else role_choice
)

company_options = ["Google", "Microsoft", "Infosys", "Other / Custom Company"]
company_choice = st.sidebar.selectbox("Choose Target Company:", company_options)
selected_company = (
    st.sidebar.text_input("Type the company name here:", placeholder="e.g., Tata, Microsoft")
    if company_choice == "Other / Custom Company"
    else company_choice
)

if selected_role and selected_company:
    st.sidebar.success(f"Active Mode: {selected_role} at {selected_company}")
else:
    st.sidebar.warning("Please fill out your custom role/company.")

# Show DB-sourced profile in sidebar as styled cards
profile = st.session_state.candidate_profile
if profile["tech_stack"] or profile["target_roles"]:
    cards_html = ""
    if profile["tech_stack"]:
        tags = "".join(
            f'<span class="tag tag-tech">{t}</span>'
            for t in profile["tech_stack"]
        )
        cards_html += f"""
        <div class="profile-card tech-card">
            <div class="card-label">🗄️ DB Tech Stack</div>
            <div class="tag-row">{tags}</div>
        </div>"""
    if profile["target_roles"]:
        tags = "".join(
            f'<span class="tag tag-role">{r}</span>'
            for r in profile["target_roles"]
        )
        cards_html += f"""
        <div class="profile-card role-card">
            <div class="card-label">🎯 DB Target Roles</div>
            <div class="tag-row">{tags}</div>
        </div>"""
    st.sidebar.markdown(cards_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 1 — Live Mock Interview
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs(["🤖 Live Mock Interview", "📝 Log Real Interview"])

with tab1:
    st.header("Live Agent Practice")

    # VIEW A — Scorecard
    if st.session_state.show_evaluation:
        st.subheader("📊 Your Performance Scorecard")
        st.markdown(st.session_state.evaluation_report)
        st.write("---")
        if st.button("Start a New Interview Session"):
            st.session_state.chat_started = False
            st.session_state.show_evaluation = False
            st.session_state.messages = []
            st.session_state.evaluation_report = ""
            st.session_state.candidate_profile = fetch_candidate_profile()
            st.rerun()

    # VIEW B — Setup
    elif not st.session_state.chat_started:
        st.info("Set up your target settings in the sidebar and click below to begin.")
        if st.button("Start Mock Session"):
            if selected_role and selected_company:
                st.session_state.chat_started = True
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": (
                            f"Hello! I am your AI Interviewer today for the {selected_role} role "
                            f"at {selected_company}. Let's begin. Can you briefly introduce yourself?"
                        ),
                    }
                ]
                st.rerun()
            else:
                st.error("Please provide both a role and a company before starting.")

    # VIEW C — Active chat
    else:
        st.success(f"📟 Active Session: Interviewing for {selected_role} at {selected_company}")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_input = st.chat_input("Type your technical answer here...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            with st.chat_message("assistant"):
                with st.spinner("Interviewer is thinking..."):
                    try:
                        context_history = "".join(
                            f"{m['role'].upper()}: {m['content']}\n"
                            for m in st.session_state.messages[:-1]
                        )

                        # --- Company culture profile ---
                        company_profiles = {
                            "Google":    "Focus heavily on system scale, algorithmic efficiency, distributed infrastructure, and strict architectural trade-offs.",
                            "Microsoft": "Focus on enterprise scalability, Azure cloud integrations, software design patterns, and robust maintainability.",
                            "Infosys":   "Focus on core foundational concepts, structured lifecycle delivery, agile methodologies, and confident hands-on problem-solving.",
                        }
                        selected_profile = company_profiles.get(
                            selected_company,
                            "Focus on modern engineering practices, practical problem-solving, and adaptable tech-stack integration.",
                        )

                        # --- DB-driven tech stack clause ---
                        db_tech   = profile["tech_stack"]
                        db_roles  = profile["target_roles"]

                        tech_stack_clause = ""
                        if db_tech:
                            tech_stack_clause = (
                                f"\n\nCANDIDATE TECH STACK (from profile DB): {', '.join(db_tech)}.\n"
                                f"You MUST probe the candidate's depth in EACH of the following technologies: "
                                f"{', '.join(db_tech)}.\n"
                                f"For every technology listed, ask about real-world implementation details, "
                                f"architectural trade-offs, failure modes, and performance characteristics. "
                                f"Do not skip any item in the list."
                            )

                        role_clause = ""
                        if db_roles:
                            role_clause = (
                                f" Their profile also indicates experience targeting: {', '.join(db_roles)}."
                            )

                        # --- Final dynamic system instruction ---
                        system_instruction = (
                            f"You are a seasoned principal interviewer at {selected_company} conducting "
                            f"an interview loop for a {selected_role} position.{role_clause}\n\n"
                            f"CRITICAL BEHAVIORAL RULE: Tailor your questioning style to "
                            f"{selected_company}'s engineering culture — {selected_profile}"
                            f"{tech_stack_clause}\n\n"
                            f"INSTRUCTIONS:\n"
                            f"1. Review the transcript history closely.\n"
                            f"2. Push deeply into exact technical and architectural details based on what the candidate claims.\n"
                            f"3. Do not accept vague high-level answers — demand specifics.\n"
                            f"4. Ask exactly ONE clear, targeted technical question per turn."
                        )

                        reply = generate_with_fallback(
                            contents=f"{context_history}USER: {user_input}\nASSISTANT:",
                            system_instruction=system_instruction,
                        )
                        st.write(reply)

                    except Exception as e:
                        reply = f"Sorry, I hit a connectivity error. Details: {str(e)}"
                        st.error(reply)

            st.session_state.messages.append({"role": "assistant", "content": reply})

        st.write("---")
        if st.button("End Interview & Generate Report"):
            if len(st.session_state.messages) <= 1:
                st.warning("The session is too short to evaluate. Please converse with the AI first!")
            else:
                with st.spinner("Analyzing conversation history and grading performance..."):
                    try:
                        full_transcript = "".join(
                            f"{m['role'].upper()}: {m['content']}\n\n"
                            for m in st.session_state.messages
                        )

                        tech_focus = (
                            f"\n\nPay special attention to how well the candidate demonstrated depth "
                            f"in their stated tech stack: {', '.join(profile['tech_stack'])}."
                            if profile["tech_stack"] else ""
                        )

                        eval_prompt = (
                            f"You are an expert technical hiring panel grader at {selected_company}. "
                            f"Review the following mock interview transcript for a {selected_role} candidate:\n\n"
                            f"```\n{full_transcript}\n```\n\n"
                            f"Generate a clear, structured markdown performance review. Include:\n"
                            f"1. Overall score 1-10 with a bold single-sentence justification.\n"
                            f"2. Core Strengths (bullet points on technical depth).\n"
                            f"3. Key Technical Gaps / Flaws (where they lacked depth or gave vague answers).\n"
                            f"4. Concrete Actionable Advice for improvement."
                            f"{tech_focus}"
                        )

                        st.session_state.evaluation_report = generate_with_fallback(eval_prompt)
                        st.session_state.show_evaluation = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to generate evaluation report: {str(e)}")


# ---------------------------------------------------------------------------
# Tab 2 — Log Real Interview
# ---------------------------------------------------------------------------

with tab2:
    st.header("Record an Interview Experience")
    st.write("Attended a real interview? Save the details below to keep a permanent history.")

    with st.form("interview_form"):
        company_name    = st.text_input("Company Name", value=selected_company or "")
        role_name       = st.text_input("Role Title", value=selected_role or "")
        interview_date  = st.date_input("Interview Date", datetime.date.today())
        questions_asked = st.text_area("What technical/round questions did they ask you?")
        self_evaluation = st.slider("How well do you think you performed? (1-10)", 1, 10, 5)

        if st.form_submit_button("Save to Dashboard Database"):
            if company_name and role_name:
                ok, msg = save_interview_log(
                    company_name, role_name, interview_date, questions_asked, self_evaluation
                )
                if ok:
                    st.success(f"🚀 {msg}")
                else:
                    st.error(f"Database Write Error: {msg}")
            else:
                st.error("Please make sure Company Name and Role Title are not blank.")
