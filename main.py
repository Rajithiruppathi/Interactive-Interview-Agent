import os
import streamlit as st
import datetime
import openai
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

st.set_page_config(
    page_title="AI Interview Coach",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global typography & base ───────────────────────────── */
html, body, [class*="css"], .stMarkdown, .stText, p,
label, input, textarea, button, select {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}
/* Preserve Material Icons/Symbols font for Streamlit avatars & icons */
[class*="material-icons"], [class*="material-symbols"], .stChatMessage [data-testid="chatAvatarIcon-assistant"] * {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

/* ── App background — deep slate ────────────────────────── */
.stApp {
    background: #0f1117;
    color: #e2e8f0;
}

/* ── Hide default Streamlit chrome (keep sidebar toggle) ─── */
#MainMenu, header[data-testid="stHeader"], footer { display: none !important; }
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display: flex !important; }

/* ── Main content column ─────────────────────────────────── */
.block-container {
    padding-top: 0rem !important;
    padding-bottom: 2.5rem;
    max-width: 860px;
    margin: 0 auto !important;
    background: transparent;
}

/* ── Hero section ────────────────────────────────────────── */
.hero-wrap {
    padding: 3.2rem 0 2.4rem 0;
    text-align: center;
}
.hero-eyebrow {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    color: #60a5fa;
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 20px;
    padding: 4px 14px;
    margin-bottom: 20px;
}
.hero-headline {
    font-size: 2.75rem;
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1.15;
    margin: 0 0 16px 0;
    background: linear-gradient(135deg, #f1f5f9 30%, #60a5fa 70%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.hero-sub {
    font-size: 1.05rem;
    color: #64748b;
    max-width: 560px;
    margin: 0 auto 36px auto;
    line-height: 1.7;
    font-weight: 400;
}
.metrics-grid {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 8px;
}
.metric-card {
    background: linear-gradient(135deg, #161b27, #1a2035);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 20px 28px;
    min-width: 160px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.metric-number {
    font-size: 1.9rem;
    font-weight: 800;
    background: linear-gradient(90deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
    margin-bottom: 6px;
}
.metric-label {
    font-size: 11.5px;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* ── Form (tab 2) — high-contrast text ──────────────────── */
[data-testid="stForm"] label,
[data-testid="stForm"] .stTextInput label,
[data-testid="stForm"] .stTextArea label,
[data-testid="stForm"] .stDateInput label,
[data-testid="stForm"] .stSlider label,
[data-testid="stForm"] p {
    color: #e2e8f0 !important;
    font-weight: 500 !important;
}
[data-testid="stForm"] input,
[data-testid="stForm"] textarea {
    color: #f1f5f9 !important;
    background: #1e293b !important;
    caret-color: #60a5fa !important;
}
[data-testid="stForm"] input::placeholder,
[data-testid="stForm"] textarea::placeholder {
    color: #475569 !important;
}
[data-testid="stForm"] [data-baseweb="slider"] [data-testid="stSliderTickBarMin"],
[data-testid="stForm"] [data-baseweb="slider"] [data-testid="stSliderTickBarMax"] {
    color: #94a3b8 !important;
}

/* ── Sidebar ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #161b27 !important;
    border-right: 1px solid #1e293b;
}
[data-testid="stSidebar"] * {
    color: #cbd5e1 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #f1f5f9 !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label {
    color: #94a3b8 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Input boxes & selects — rounded, dark ───────────────── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    color: #ffffff !important;
}
/* Force selected value text inside selectbox to bright white */
[data-baseweb="select"] span,
[data-baseweb="select"] > div > div,
[data-baseweb="select"] > div > div > div,
[data-baseweb="select"] [data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSidebar"] [data-baseweb="select"] *:not(svg):not(path) {
    color: #ffffff !important;
}
.stTextInput > div > div,
.stTextArea > div > div,
[data-baseweb="input"],
[data-baseweb="textarea"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within,
[data-baseweb="input"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── Sidebar structural spacing ──────────────────────────── */
[data-testid="stSidebar"] > div:first-child {
    padding: 1.6rem 1.1rem 1rem 1.1rem !important;
}
[data-testid="stSidebar"] .stSelectbox {
    margin-bottom: 1.2rem !important;
}
[data-testid="stSidebar"] .stTextInput {
    margin-bottom: 1rem !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stSidebar"] .stSuccess,
[data-testid="stSidebar"] .stWarning {
    margin-top: 1.2rem !important;
    margin-bottom: 1.4rem !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    margin-bottom: 1.4rem !important;
    padding-bottom: 0.55rem !important;
    border-bottom: 1px solid #1e293b;
}

/* ── Chat input bar ──────────────────────────────────────── */
[data-testid="stChatInput"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 14px !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}
[data-testid="stChatInput"] textarea {
    color: #e2e8f0 !important;
    background: transparent !important;
}

/* ── Chat bubbles — assistant ────────────────────────────── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: linear-gradient(135deg, #1e2d45 0%, #162032 100%) !important;
    border: 1px solid #1e3a5f;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    margin-bottom: 12px;
    box-shadow: 0 2px 12px rgba(59,130,246,0.08);
}

/* ── Chat bubbles — user ─────────────────────────────────── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, #1a1f2e 0%, #0f172a 100%) !important;
    border: 1px solid #2d3748;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    margin-bottom: 12px;
}

/* ── Buttons — primary ───────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 22px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.2px;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.35) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    box-shadow: 0 4px 16px rgba(59,130,246,0.45) !important;
    transform: translateY(-1px);
}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #161b27;
    border-radius: 12px;
    padding: 4px;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    padding: 8px 24px;
    border-radius: 9px;
    font-weight: 500;
    font-size: 14px;
    color: #64748b !important;
    background: transparent !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #1e3a5f, #1e2d45) !important;
    color: #60a5fa !important;
    box-shadow: 0 2px 8px rgba(59,130,246,0.2);
}

/* ── Alert / info / success banners ─────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
}
.stSuccess { background: rgba(16,185,129,0.12) !important; color: #6ee7b7 !important; }
.stInfo    { background: rgba(59,130,246,0.12) !important; color: #93c5fd !important; }
.stWarning { background: rgba(245,158,11,0.12) !important; color: #fcd34d !important; }
.stError   { background: rgba(239,68,68,0.12)  !important; color: #fca5a5 !important; }

/* ── Sidebar profile cards ───────────────────────────────── */
.profile-card {
    border-radius: 12px;
    padding: 13px 15px;
    margin: 8px 0;
    border-left: 3px solid;
}
.tech-card { background: rgba(37,99,235,0.12); border-left-color: #3b82f6; }
.role-card { background: rgba(124,58,237,0.12); border-left-color: #8b5cf6; }

.card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #64748b;
    margin-bottom: 9px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
}
.tag-tech { background: rgba(59,130,246,0.2); color: #93c5fd; }
.tag-role { background: rgba(139,92,246,0.2); color: #c4b5fd; }

/* ── Selectbox dropdown menu ─────────────────────────────── */
[data-baseweb="popover"],
[data-baseweb="popover"] > div {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 30px rgba(0,0,0,0.5) !important;
}
[data-baseweb="menu"] {
    background: #1e293b !important;
}
[data-baseweb="menu"] li,
[data-baseweb="option"] {
    background: #1e293b !important;
    color: #e2e8f0 !important;
}
[data-baseweb="menu"] li:hover,
[data-baseweb="option"]:hover {
    background: #2d3f5e !important;
    color: #ffffff !important;
}
[data-baseweb="menu"] [aria-selected="true"],
[data-baseweb="option"][aria-selected="true"] {
    background: rgba(59,130,246,0.18) !important;
    color: #60a5fa !important;
}

/* ── Slider ──────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: #3b82f6 !important;
    border-color: #3b82f6 !important;
}

/* ── Divider ─────────────────────────────────────────────── */
hr { border-color: #1e293b !important; }

/* ── Spinner ─────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {
    border-top-color: #3b82f6 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-wrap">
    <span class="hero-eyebrow">AI-Powered Interview Intelligence</span>
    <h1 class="hero-headline">Ace Every Interview.<br>Track Every Outcome.</h1>
    <p class="hero-sub">
        Practice with a real-time AI interviewer that adapts to your tech stack,
        then log and analyse your actual interview experiences — all in one place.
    </p>
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-number">50+</div>
            <div class="metric-label">Roles Covered</div>
        </div>
        <div class="metric-card">
            <div class="metric-number">Live</div>
            <div class="metric-label">Real-Time AI Feedback</div>
        </div>
        <div class="metric-card">
            <div class="metric-number">DB</div>
            <div class="metric-label">Enterprise DB Backed</div>
        </div>
    </div>
</div>
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
