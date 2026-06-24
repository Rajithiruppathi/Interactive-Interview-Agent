import os
import streamlit as st
import datetime
import openai
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

# Set up the title of your app
st.title("🎙️ Interactive Interview & Tracker Dashboard")
st.write("Select your target role or log your real-world interview experiences.")

# --- INITIALIZE CLIENTS ---
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
    st.error("Could not load Gemini Client. Please ensure your GEMINI_API_KEY environment variable is set.")

def _is_rate_limit(err: Exception) -> bool:
    msg = str(err).upper()
    return any(t in msg for t in ("429", "503", "RESOURCE_EXHAUSTED", "QUOTA", "RATE_LIMIT", "UNAVAILABLE", "HIGH DEMAND"))

def generate_with_fallback(contents: str, system_instruction: str = "") -> str:
    # --- Gemini (primary) ---
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

    # --- OpenAI (silent fallback on quota exhaustion) ---
    oai = get_openai_client()
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": contents})
    resp = oai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return resp.choices[0].message.content

# --- INITIALIZE SESSION STATES ---
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_evaluation" not in st.session_state:
    st.session_state.show_evaluation = False
if "evaluation_report" not in st.session_state:
    st.session_state.evaluation_report = ""


# --- SIDEBAR: Configuration Options ---
st.sidebar.header("🎯 Target Interview Settings")

role_options = [
    "AI Engineer",
    "Generative AI Developer",
    "Python Backend Developer",
    "Data Scientist",
    "Other / Custom Role",
]
role_choice = st.sidebar.selectbox("Choose Target Role:", role_options)

if role_choice == "Other / Custom Role":
    selected_role = st.sidebar.text_input(
        "Type your specific role/stream here:", placeholder="e.g., Frontend Developer"
    )
else:
    selected_role = role_choice

company_options = ["Google", "Microsoft", "Infosys", "Other / Custom Company"]
company_choice = st.sidebar.selectbox("Choose Target Company:", company_options)

if company_choice == "Other / Custom Company":
    selected_company = st.sidebar.text_input(
        "Type the company name here:", placeholder="e.g., Tata, Microsoft"
    )
else:
    selected_company = company_choice


if selected_role and selected_company:
    st.sidebar.success(f"Active Mode: {selected_role} at {selected_company}")
else:
    st.sidebar.warning("Please fill out your custom role/company.")


# --- MAIN PAGE TABS ---
tab1, tab2 = st.tabs(["🤖 Live Mock Interview", "📝 Log Real Interview"])

with tab1:
    st.header("Live Agent Practice")

    # VIEW A: Evaluation Report Page
    if st.session_state.show_evaluation:
        st.subheader("📊 Your Performance Scorecard")
        st.markdown(st.session_state.evaluation_report)
        
        st.write("---")
        if st.button("Start a New Interview Session"):
            st.session_state.chat_started = False
            st.session_state.show_evaluation = False
            st.session_state.messages = []
            st.session_state.evaluation_report = ""
            st.rerun()

    # VIEW B: Welcome / Setup view
    elif not st.session_state.chat_started:
        st.info("Set up your target settings in the sidebar and click below to begin.")

        if st.button("Start Mock Session"):
            if selected_role and selected_company:
                st.session_state.chat_started = True
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": f"Hello! I am your AI Interviewer today for the {selected_role} role at {selected_company}. Let's begin. Can you briefly introduce yourself?",
                    }
                ]
                st.rerun()
            else:
                st.error("Please provide both a role and a company before starting.")

    # VIEW C: Active Chat conversation elements
    else:
        st.success(
            f"📟 Active Session: Interviewing for {selected_role} at {selected_company}"
        )

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
                        context_history = ""
                        for msg in st.session_state.messages[:-1]:
                            context_history += f"{msg['role'].upper()}: {msg['content']}\n"
                        
                        system_instruction = (
                            f"You are a professional, technical recruiter conducting a rigorous interview at {selected_company}. "
                            f"You are evaluating a candidate for a {selected_role} position. "
                            f"Analyze their experience details carefully. Keep your comments concise, push deeply into specific "
                            f"technical architectural metrics based on what they claim, and ask exactly one clear technical question at a time."
                        )
                        
                        reply = generate_with_fallback(
                            contents=f"{context_history}USER: {user_input}\nASSISTANT:",
                            system_instruction=system_instruction,
                        )
                        st.write(reply)
                        
                    except Exception as e:
                        reply = f"Sorry, I hit an interface connectivity error. Technical details: {str(e)}"
                        st.error(reply)
            
            st.session_state.messages.append({"role": "assistant", "content": reply})

        # Add the Evaluation trigger here!
        st.write("---")
        if st.button("End Interview & Generate Report"):
            if len(st.session_state.messages) <= 1:
                st.warning("The session is too short to evaluate. Please converse with the AI first!")
            else:
                with st.spinner("Analyzing conversation history and grading performance..."):
                    try:
                        # Build full transcript text
                        full_transcript = ""
                        for msg in st.session_state.messages:
                            full_transcript += f"{msg['role'].upper()}: {msg['content']}\n\n"
                        
                        eval_prompt = (
                            f"You are an expert technical hiring panel grader at {selected_company}. "
                            f"Review the following mock interview transcript for an engineering candidate applying for the {selected_role} position:\n\n"
                            f"```\n{full_transcript}\n```\n\n"
                            f"Generate a clear, beautifully structured markdown performance review report. Include:\n"
                            f"1. An overall score from 1-10 with a bold single-sentence justification.\n"
                            f"2. Core Strengths (Bullet points analyzing their technical descriptions).\n"
                            f"3. Key Technical Gaps / Flaws (Where they lacked depth or gave short answers).\n"
                            f"4. Concrete Actionable Advice on how to perform better next time."
                        )
                        
                        st.session_state.evaluation_report = generate_with_fallback(eval_prompt)
                        st.session_state.show_evaluation = True
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Failed to generate evaluation report: {str(e)}")


with tab2:
    st.header("Record an Interview Experience")
    st.write("Attended a real interview? Save the details below to keep a permanent history.")

    with st.form("interview_form"):
        company_name = st.text_input("Company Name", value=selected_company if selected_company else "")
        role_name = st.text_input("Role Title", value=selected_role if selected_role else "")
        interview_date = st.date_input("Interview Date", datetime.date.today())
        questions_asked = st.text_area("What technical/round questions did they ask you?")
        self_evaluation = st.slider("How well do you think you performed? (1-10)", 1, 10, 5)

        submit_button = st.form_submit_button("Save to Dashboard Database")
        if submit_button:
            if company_name and role_name:
                st.success(f"Saved! Logged {role_name} interview at {company_name}. Ready to link this data to Neon DB next!")
            else:
                st.error("Please make sure Company Name and Role Title are not blank before saving.")