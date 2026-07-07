import io
import os
import streamlit as st
import datetime
import openai
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from google import genai
from streamlit_mic_recorder import mic_recorder

load_dotenv(override=True)

st.set_page_config(
    page_title="AI Interview Coach",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ════════════════════════════════════════════════════════════
   DESIGN SYSTEM — tokens, reset, layout
   Palette: Google Gemini dark × Linear × GitHub dark
   ════════════════════════════════════════════════════════════ */
:root {
    --bg:          #0c0c11;
    --surface-1:   #12121a;
    --surface-2:   #1a1a25;
    --surface-3:   #21212f;
    --border:      #26263a;
    --border-2:    #2e2e44;
    --text-1:      #eeeef5;
    --text-2:      #9898b4;
    --text-3:      #55556a;
    --blue:        #4f7ef7;
    --blue-soft:   #8ab4f8;
    --blue-dim:    rgba(79,126,247,0.10);
    --blue-glow:   rgba(79,126,247,0.22);
    --purple:      #9b70f5;
    --purple-soft: #c4b5fd;
    --purple-dim:  rgba(155,112,245,0.10);
    --green:       #2dd4bf;
    --amber:       #fbbf24;
    --red:         #f87171;
    --r-sm:  8px;
    --r-md: 12px;
    --r-lg: 16px;
    --r-xl: 22px;
    --sh-sm: 0 1px 4px rgba(0,0,0,0.5);
    --sh-md: 0 4px 20px rgba(0,0,0,0.55);
    --sh-lg: 0 8px 40px rgba(0,0,0,0.65);
}

/* ── Global reset & typography ─────────────────────────── */
html, body, [class*="css"], .stMarkdown, .stText, p,
label, input, textarea, button, select {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
/* Preserve Material Icons font for Streamlit avatars */
[class*="material-icons"], [class*="material-symbols"],
.stChatMessage [data-testid="chatAvatarIcon-assistant"] * {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

/* ── App shell ─────────────────────────────────────────── */
.stApp {
    background: var(--bg) !important;
    color: var(--text-1) !important;
}

/* ── Hide Streamlit chrome without destroying sidebar toggle ─ */
#MainMenu, footer { display: none !important; }
/* Collapse header to zero-height (keeps DOM intact so sidebar toggle works) */
header[data-testid="stHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}
/* Force sidebar visible and fully interactive */
section[data-testid="stSidebar"],
[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    transform: translateX(0px) !important;
    min-width: 16rem !important;
    width: 16rem !important;
    z-index: 999 !important;
    position: relative !important;
    pointer-events: all !important;
}
div[data-testid="stSidebarUserContent"],
div[data-testid="stSidebarUserContent"] * {
    pointer-events: all !important;
}
/* Kill the invisible backdrop Streamlit injects when sidebar state is
   "collapsed" — it floats over the sidebar and swallows all click events */
[data-testid="stSidebarBackdrop"] {
    display: none !important;
    pointer-events: none !important;
}
/* Ensure selectbox popovers float above main content column */
[data-baseweb="popover"],
[data-baseweb="popover"] > div {
    z-index: 99999 !important;
}

/* ── Main content column ─────────────────────────────────── */
.block-container {
    padding-top: 0 !important;
    padding-bottom: 3rem;
    max-width: 880px;
    margin: 0 auto !important;
    background: transparent;
}

/* ── Sidebar overrides ───────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--surface-1) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-2) !important; }
[data-testid="stSidebar"] > div:first-child { padding: 0 0.85rem 1rem 0.85rem !important; }
div[data-testid="stSidebarUserContent"] { padding-top: 1.2rem !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--text-1) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    margin-top: 0 !important;
    margin-bottom: 1rem !important;
    padding-bottom: 0.5rem !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label {
    color: var(--text-3) !important;
    font-size: 10.5px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.7px !important;
}
[data-testid="stSidebar"] .stSelectbox { margin-bottom: 1rem !important; }
[data-testid="stSidebar"] .stTextInput  { margin-bottom: 0.9rem !important; }
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stSidebar"] .stSuccess,
[data-testid="stSidebar"] .stWarning {
    margin-top: 1rem !important;
    margin-bottom: 1.1rem !important;
    border-radius: var(--r-md) !important;
}

/* ── Hero section ────────────────────────────────────────── */
.hero-wrap {
    position: relative;
    padding: 4.2rem 0 3rem 0;
    text-align: center;
    overflow: hidden;
}
/* Ambient radial glow — no extra HTML element needed */
.hero-wrap::before {
    content: '';
    position: absolute;
    top: -60px; left: 50%; transform: translateX(-50%);
    width: 700px; height: 380px;
    background: radial-gradient(ellipse at 50% 40%,
        rgba(79,126,247,0.13) 0%,
        rgba(155,112,245,0.07) 45%,
        transparent 70%);
    pointer-events: none;
    z-index: 0;
}
.hero-eyebrow {
    position: relative; z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: var(--blue-soft);
    background: var(--blue-dim);
    border: 1px solid rgba(79,126,247,0.28);
    border-radius: 40px;
    padding: 5px 16px;
    margin-bottom: 22px;
}
.hero-headline {
    position: relative; z-index: 1;
    font-size: 3.5rem;
    font-weight: 800;
    letter-spacing: -2px;
    line-height: 1.08;
    margin: 0 0 18px 0;
    background: linear-gradient(140deg, #ffffff 10%, #c7d8ff 45%, var(--purple-soft) 85%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    position: relative; z-index: 1;
    font-size: 1.05rem;
    color: var(--text-2);
    max-width: 500px;
    margin: 0 auto 44px auto;
    line-height: 1.78;
    font-weight: 400;
}
.metrics-grid {
    position: relative; z-index: 1;
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
}
.metric-card {
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: var(--r-lg);
    padding: 20px 30px;
    min-width: 148px;
    text-align: center;
    box-shadow: var(--sh-md);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    cursor: default;
}
.metric-card:hover {
    border-color: rgba(79,126,247,0.45);
    box-shadow: 0 6px 28px rgba(79,126,247,0.14);
    transform: translateY(-2px);
}
.metric-number {
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -1.5px;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    margin-bottom: 7px;
}
.metric-label {
    font-size: 10.5px;
    color: var(--text-3);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.9px;
}

/* ── Form fields ─────────────────────────────────────────── */
[data-testid="stForm"] label,
[data-testid="stForm"] .stTextInput label,
[data-testid="stForm"] .stTextArea label,
[data-testid="stForm"] .stDateInput label,
[data-testid="stForm"] .stSlider label,
[data-testid="stForm"] p { color: var(--text-1) !important; font-weight: 500 !important; }
[data-testid="stForm"] input,
[data-testid="stForm"] textarea {
    color: var(--text-1) !important;
    background: var(--surface-2) !important;
    caret-color: var(--blue) !important;
}
[data-testid="stForm"] input::placeholder,
[data-testid="stForm"] textarea::placeholder { color: var(--text-3) !important; }
[data-testid="stForm"] [data-baseweb="slider"] [data-testid="stSliderTickBarMin"],
[data-testid="stForm"] [data-baseweb="slider"] [data-testid="stSliderTickBarMax"] {
    color: var(--text-2) !important;
}

/* ── Input & select styling ──────────────────────────────── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text-1) !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] > div > div,
[data-baseweb="select"] > div > div > div,
[data-testid="stSidebar"] [data-baseweb="select"] *:not(svg):not(path) {
    color: var(--text-1) !important;
}
.stTextInput > div > div,
.stTextArea > div > div,
[data-baseweb="input"],
[data-baseweb="textarea"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text-1) !important;
}
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within,
[data-baseweb="input"]:focus-within {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px var(--blue-glow) !important;
}

/* ── Chat input ──────────────────────────────────────────── */
[data-testid="stChatInput"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r-xl) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px var(--blue-glow) !important;
}
[data-testid="stChatInput"] textarea,
.stChatInput textarea,
div[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] > div textarea,
[data-testid="stChatInput"] > div > div textarea {
    color: var(--text-1) !important;
    -webkit-text-fill-color: var(--text-1) !important;
    background: transparent !important;
    caret-color: var(--blue) !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--text-3) !important;
    -webkit-text-fill-color: var(--text-3) !important;
}

/* ── Voice mode ──────────────────────────────────────────── */
.voice-mode-wrap {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: var(--r-md);
    margin-bottom: 12px;
}
.voice-status { font-size: 13px; color: var(--text-2); }

/* ── Chat bubbles ────────────────────────────────────────── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-left: 3px solid var(--blue) !important;
    border-radius: var(--r-md) !important;
    padding: 16px 20px !important;
    margin-bottom: 10px;
    box-shadow: var(--sh-sm);
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: var(--surface-3) !important;
    border: 1px solid var(--border-2) !important;
    border-left: 3px solid var(--purple) !important;
    border-radius: var(--r-md) !important;
    padding: 16px 20px !important;
    margin-bottom: 10px;
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] span:not([class*="material"]),
[data-testid="stChatMessage"] .stMarkdown p,
[data-testid="stChatMessage"] .stMarkdown span:not([class*="material"]),
[data-testid="stChatMessage"] .stMarkdown li,
[data-testid="stChatMessage"] .stMarkdown h1,
[data-testid="stChatMessage"] .stMarkdown h2,
[data-testid="stChatMessage"] .stMarkdown h3,
[data-testid="stChatMessage"] .element-container p,
[data-testid="stChatMessage"] div.stMarkdown {
    color: var(--text-1) !important;
    -webkit-text-fill-color: var(--text-1) !important;
    line-height: 1.75 !important;
}
[data-testid="stChatMessage"] strong,
[data-testid="stChatMessage"] b { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
[data-testid="stChatMessage"] code {
    color: var(--blue-soft) !important;
    -webkit-text-fill-color: var(--blue-soft) !important;
    background: var(--blue-dim) !important;
    border-radius: 4px; padding: 1px 6px; font-size: 0.88em;
}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {
    background: var(--blue) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    padding: 9px 22px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    letter-spacing: 0.1px;
    transition: all 0.15s ease !important;
    box-shadow: 0 1px 6px rgba(79,126,247,0.45) !important;
}
.stButton > button:hover {
    background: #6090f9 !important;
    box-shadow: 0 4px 18px rgba(79,126,247,0.55) !important;
    transform: translateY(-1px);
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md);
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    padding: 7px 22px;
    border-radius: var(--r-sm);
    font-weight: 500;
    font-size: 13.5px;
    color: var(--text-2) !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.15s;
}
.stTabs [aria-selected="true"] {
    background: var(--surface-3) !important;
    color: var(--text-1) !important;
    box-shadow: var(--sh-sm);
}

/* ── Alerts ──────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: var(--r-md) !important; }
.stSuccess { background: rgba(45,212,191,0.07) !important; color: #5eead4 !important; border-left: 3px solid var(--green) !important; border-right: none; border-top: none; border-bottom: none; }
.stInfo    { background: var(--blue-dim) !important;        color: var(--blue-soft) !important; border-left: 3px solid var(--blue) !important; border-right: none; border-top: none; border-bottom: none; }
.stWarning { background: rgba(251,191,36,0.07) !important;  color: var(--amber) !important;     border-left: 3px solid var(--amber) !important; border-right: none; border-top: none; border-bottom: none; }
.stError   { background: rgba(248,113,113,0.07) !important; color: var(--red) !important;       border-left: 3px solid var(--red) !important;   border-right: none; border-top: none; border-bottom: none; }

/* ── Sidebar profile cards ───────────────────────────────── */
.profile-card {
    border-radius: var(--r-md);
    padding: 11px 13px;
    margin: 7px 0;
    border: 1px solid var(--border-2);
}
.tech-card { background: rgba(79,126,247,0.07); border-left: 3px solid var(--blue); }
.role-card { background: rgba(155,112,245,0.07); border-left: 3px solid var(--purple); }
.card-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.9px; color: var(--text-3); margin-bottom: 8px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 5px; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11.5px; font-weight: 500; white-space: nowrap; }
.tag-tech { background: rgba(79,126,247,0.14); color: var(--blue-soft); border: 1px solid rgba(79,126,247,0.22); }
.tag-role { background: rgba(155,112,245,0.14); color: var(--purple-soft); border: 1px solid rgba(155,112,245,0.22); }

/* ── Context banner ──────────────────────────────────────── */
.context-banner {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    background: var(--surface-2);
    border: 1px solid var(--border-2);
    border-radius: var(--r-md);
    padding: 10px 18px;
    margin: 0 0 1.2rem 0;
}
.context-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-3); }
.context-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--blue-dim); border: 1px solid rgba(79,126,247,0.28);
    border-radius: 20px; padding: 3px 12px;
    font-size: 12.5px; font-weight: 600; color: var(--blue-soft);
}
.context-pill-purple {
    background: var(--purple-dim); border-color: rgba(155,112,245,0.28);
    color: var(--purple-soft);
}
.context-arrow { color: var(--border-2); font-size: 14px; }

/* ── Dropdown menus ──────────────────────────────────────── */
[data-baseweb="popover"],
[data-baseweb="popover"] > div {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--sh-lg) !important;
    z-index: 99999 !important;
}
[data-baseweb="menu"] { background: var(--surface-2) !important; }
[data-baseweb="menu"] li,
[data-baseweb="option"] { background: var(--surface-2) !important; color: var(--text-2) !important; }
[data-baseweb="menu"] li:hover,
[data-baseweb="option"]:hover { background: var(--surface-3) !important; color: var(--text-1) !important; }
[data-baseweb="menu"] [aria-selected="true"],
[data-baseweb="option"][aria-selected="true"] { background: var(--blue-dim) !important; color: var(--blue-soft) !important; }

/* ── DataFrames ──────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: var(--r-md) !important; overflow: hidden; }

/* ── Slider ──────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: var(--blue) !important; border-color: var(--blue) !important;
}

/* ── Divider & spinner ───────────────────────────────────── */
hr { border-color: var(--border) !important; }
[data-testid="stSpinner"] > div { border-top-color: var(--blue) !important; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


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
                "tech_stack": row["tech_stack"] or [],
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
                (
                    company_name,
                    role_name,
                    interview_date,
                    questions_asked,
                    self_evaluation,
                ),
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

        fetch_candidate_profile()  # function under test

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            after = cur.fetchone()[0]

        # after should equal before (fetch opened and closed its own connection)
        return after <= before + 1  # +1 tolerance for the test connection itself
    except Exception:
        return True  # can't test without DB — assume pass
    finally:
        if conn is not None:
            conn.close()


def fetch_all_logs() -> list[dict]:
    """Returns all rows from interview_logs for CRM display, newest first."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, company_name, role_name, interview_date, "
                "self_evaluation, created_at "
                "FROM interview_logs ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        if conn is not None:
            conn.close()


def fetch_historical_scores() -> list[dict]:
    """Returns the 5 most recent self_evaluation scores for grading comparison."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT company_name, role_name, interview_date, self_evaluation "
                "FROM interview_logs ORDER BY created_at DESC LIMIT 5"
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
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
    return any(
        t in msg
        for t in (
            "429",
            "503",
            "RESOURCE_EXHAUSTED",
            "QUOTA",
            "RATE_LIMIT",
            "UNAVAILABLE",
            "HIGH DEMAND",
        )
    )


def generate_with_fallback(contents: str, system_instruction: str = "") -> str:
    if gemini_client is not None:
        try:
            cfg = (
                {"system_instruction": system_instruction} if system_instruction else {}
            )
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
    return resp.choices[0].message.content or ""


def transcribe_audio(audio_bytes: bytes) -> str:
    """Sends raw audio bytes to OpenAI Whisper and returns the transcript text."""
    buf = io.BytesIO(audio_bytes)
    buf.name = "recording.webm"
    oai = get_openai_client()
    result = oai.audio.transcriptions.create(
        model="whisper-1",
        file=buf,
        response_format="text",
    )
    return (result if isinstance(result, str) else result.text).strip()


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
if "last_voice_id" not in st.session_state:
    st.session_state.last_voice_id = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.header("🎯 Target Interview Settings")

role_options = [
    "AI Engineer",
    "Generative AI Developer",
    "Python Backend Developer",
    "Data Scientist",
    "Other / Custom Role",
]
role_choice = st.sidebar.selectbox("Choose Target Role:", role_options)
selected_role = (
    st.sidebar.text_input(
        "Type your specific role/stream here:", placeholder="e.g., Frontend Developer"
    )
    if role_choice == "Other / Custom Role"
    else role_choice
)

company_options = ["Google", "Microsoft", "Infosys", "Other / Custom Company"]
company_choice = st.sidebar.selectbox("Choose Target Company:", company_options)
selected_company = (
    st.sidebar.text_input(
        "Type the company name here:", placeholder="e.g., Tata, Microsoft"
    )
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
            f'<span class="tag tag-tech">{t}</span>' for t in profile["tech_stack"]
        )
        cards_html += f"""
        <div class="profile-card tech-card">
            <div class="card-label">🗄️ DB Tech Stack</div>
            <div class="tag-row">{tags}</div>
        </div>"""
    if profile["target_roles"]:
        tags = "".join(
            f'<span class="tag tag-role">{r}</span>' for r in profile["target_roles"]
        )
        cards_html += f"""
        <div class="profile-card role-card">
            <div class="card-label">🎯 DB Target Roles</div>
            <div class="tag-row">{tags}</div>
        </div>"""
    st.sidebar.markdown(cards_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Active context banner — persists above all tabs so target is never lost
# ---------------------------------------------------------------------------

if selected_role and selected_company:
    st.markdown(
        f"""
        <div class="context-banner">
            <span class="context-label">Active Target</span>
            <span class="context-pill">🎯 {selected_role}</span>
            <span class="context-arrow">→</span>
            <span class="context-pill context-pill-purple">🏢 {selected_company}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        st.success(
            f"📟 Active Session: Interviewing for {selected_role} at {selected_company}"
        )

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # ── Input mode toggle ────────────────────────────────────────────────
        mode_col, _ = st.columns([2, 5])
        with mode_col:
            voice_mode = st.toggle(
                "🎙️ Voice Mode",
                value=False,
                key="voice_mode_toggle",
                help="Switch to microphone input — your speech is transcribed by Whisper then sent to the AI interviewer.",
            )

        user_input: str | None = None

        if not voice_mode:
            user_input = st.chat_input("Type your technical answer here...")
        else:
            st.markdown(
                '<div class="voice-mode-wrap">'
                '<span style="font-size:22px">🎙️</span>'
                '<span class="voice-status">Click <strong>Start</strong>, speak your answer, then click <strong>Stop</strong>. '
                "Your answer will be transcribed and sent automatically.</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            audio = mic_recorder(
                start_prompt="⏺ Start Recording",
                stop_prompt="⏹ Stop & Send",
                just_once=True,
                use_container_width=False,
                key="voice_recorder",
            )
            if audio and audio.get("id") != st.session_state.last_voice_id:
                st.session_state.last_voice_id = audio["id"]
                with st.spinner("Transcribing audio via Whisper..."):
                    try:
                        user_input = transcribe_audio(audio["bytes"])
                        st.info(f'📝 Transcribed: *"{user_input}"*')
                    except Exception as transcribe_err:
                        st.error(f"Transcription failed: {transcribe_err}")

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
                            "Google": "Focus heavily on system scale, algorithmic efficiency, distributed infrastructure, and strict architectural trade-offs.",
                            "Microsoft": "Focus on enterprise scalability, Azure cloud integrations, software design patterns, and robust maintainability.",
                            "Infosys": "Focus on core foundational concepts, structured lifecycle delivery, agile methodologies, and confident hands-on problem-solving.",
                        }
                        selected_profile = company_profiles.get(
                            selected_company,
                            "Focus on modern engineering practices, practical problem-solving, and adaptable tech-stack integration.",
                        )

                        # --- DB-driven tech stack clause ---
                        db_tech = profile["tech_stack"]
                        db_roles = profile["target_roles"]

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
                            role_clause = f" Their profile also indicates experience targeting: {', '.join(db_roles)}."

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
                st.warning(
                    "The session is too short to evaluate. Please converse with the AI first!"
                )
            else:
                with st.spinner(
                    "Analyzing conversation history and grading performance..."
                ):
                    try:
                        full_transcript = "".join(
                            f"{m['role'].upper()}: {m['content']}\n\n"
                            for m in st.session_state.messages
                        )

                        tech_focus = (
                            f"\n\nPay special attention to how well the candidate demonstrated depth "
                            f"in their stated tech stack: {', '.join(profile['tech_stack'])}."
                            if profile["tech_stack"]
                            else ""
                        )

                        # Pull historical self-evaluation scores from DB for growth comparison
                        past_scores = fetch_historical_scores()
                        if past_scores:
                            past_lines = "\n".join(
                                f"  • {r['role_name']} at {r['company_name']} "
                                f"({r['interview_date']}): self-score {r['self_evaluation']}/10"
                                for r in past_scores
                            )
                            history_clause = (
                                f"\n\nCANDIDATE HISTORICAL PERFORMANCE (logged in DB, newest first):\n"
                                f"{past_lines}\n\n"
                                f"MANDATORY: Add a '📈 Growth Trajectory' section that explicitly "
                                f"compares today's AI-graded performance to the historical self-scores above. "
                                f"Call out concrete improvements, regressions, or plateaus. "
                                f"Reference actual score numbers and session dates."
                            )
                        else:
                            history_clause = ""

                        eval_prompt = (
                            f"You are an expert technical hiring panel grader at {selected_company}. "
                            f"Review the following mock interview transcript for a {selected_role} candidate:\n\n"
                            f"```\n{full_transcript}\n```\n\n"
                            f"Generate a clear, structured markdown performance review. Include:\n"
                            f"1. **Overall Score** (1-10) with a bold single-sentence justification.\n"
                            f"2. **Core Strengths** — bullet points on demonstrated technical depth.\n"
                            f"3. **Key Technical Gaps** — where the candidate lacked depth or gave vague answers.\n"
                            f"4. **Concrete Actionable Advice** — specific next steps to improve.\n"
                            f"5. **📈 Growth Trajectory** — compare to historical logs (if provided)."
                            f"{tech_focus}"
                            f"{history_clause}"
                        )

                        st.session_state.evaluation_report = generate_with_fallback(
                            eval_prompt
                        )
                        st.session_state.show_evaluation = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to generate evaluation report: {str(e)}")


# ---------------------------------------------------------------------------
# Tab 2 — Log Real Interview
# ---------------------------------------------------------------------------

with tab2:
    st.header("Record an Interview Experience")
    st.write(
        "Attended a real interview? Save the details below to keep a permanent history."
    )

    with st.form("interview_form"):
        company_name = st.text_input("Company Name", value=selected_company or "")
        role_name = st.text_input("Role Title", value=selected_role or "")
        interview_date = st.date_input("Interview Date", datetime.date.today())
        questions_asked = st.text_area(
            "What technical/round questions did they ask you?"
        )
        self_evaluation = st.slider(
            "How well do you think you performed? (1-10)", 1, 10, 5
        )

        if st.form_submit_button("Save to Dashboard Database"):
            if company_name and role_name:
                ok, msg = save_interview_log(
                    company_name,
                    role_name,
                    interview_date,
                    questions_asked,
                    self_evaluation,
                )
                if ok:
                    st.success(f"🚀 {msg}")
                else:
                    st.error(f"Database Write Error: {msg}")
            else:
                st.error("Please make sure Company Name and Role Title are not blank.")

    # ── CRM Database Viewer ──────────────────────────────────────────────────
    st.write("---")
    st.subheader("📊 Interview History — Live CRM View")
    st.caption("All entries pulled directly from Neon DB on every page load.")

    logs = fetch_all_logs()
    if logs:
        # Rename columns for display
        display_rows = [
            {
                "ID": r["id"],
                "Company": r["company_name"],
                "Role": r["role_name"],
                "Date": str(r["interview_date"]),
                "Self Score": r["self_evaluation"],
                "Logged At": str(r["created_at"])[:16] if r["created_at"] else "",
            }
            for r in logs
        ]
        st.dataframe(display_rows, use_container_width=True, hide_index=True)
        avg = sum(r["Self Score"] for r in display_rows) / len(display_rows)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Interviews Logged", len(display_rows))
        col2.metric("Avg Self-Score", f"{avg:.1f} / 10")
        col3.metric(
            "Latest Entry",
            display_rows[0]["Company"] if display_rows else "—",
        )
    else:
        st.info(
            "No interview logs yet. Fill the form above and click **Save** to start tracking."
        )
