import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime

st.set_page_config(page_title="UB Med Practice Generator", page_icon="🩺", layout="wide")

GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
BIN_ID = st.secrets.get("JSONBIN_BIN_ID", "")
JSONBIN_KEY = st.secrets.get("JSONBIN_API_KEY", "")

if not GEMINI_KEY or not BIN_ID or not JSONBIN_KEY:
    st.error("🔑 API Keys or DB Credentials missing in Streamlit Secrets!")
    st.stop()

genai.configure(api_key=GEMINI_KEY)

# Use gemini-2.5-pro for NotebookLM-grade reasoning and full document comprehension
model = genai.GenerativeModel("models/gemini-2.5-pro")

def load_cloud_data():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            raw_data = req.json().get("record", {})
            return {k: v for k, v in raw_data.items() if isinstance(v, dict) and "sessions" in v}
    except Exception as e:
        st.error(f"Error reading database: {e}")
    return {}

st.title("🎓 Student Practice Question Generator")
st.caption("Select your course and lecture sessions to generate board-style practice questions.")

data = load_cloud_data()

if not data:
    st.info("No active courses are currently available. Please check back after faculty publish a course.")
    st.stop()

selected_course = st.selectbox("Select Course:", options=list(data.keys()))
course_info = data.get(selected_course, {})
sessions_dict = course_info.get("sessions", {})
global_course_style = course_info.get("global_style_profile", "")

if not sessions_dict:
    st.warning(f"No lecture sessions available for '{selected_course}' yet.")
    st.stop()

def sort_key(item):
    title, details = item
    raw_date = details.get("date", "2099-12-31")
    return (raw_date, title.lower())

sorted_sessions = sorted(sessions_dict.items(), key=sort_key)

st.markdown("---")
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Select Lecture Sessions")
    st.caption("Check the sessions you want to practice:")
    
    selected_session_titles = []
    
    for title, details in sorted_sessions:
        raw_date = details.get("date", "")
        formatted_date = ""
        if raw_date:
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d")
                formatted_date = dt.strftime("%m/%d/%Y") + " - "
            except ValueError:
                formatted_date = ""
        
        display_label = f"{formatted_date}{title}"
        if st.checkbox(display_label, key=f"cb_{selected_course}_{title}"):
            selected_session_titles.append(title)
            
    st.markdown("---")
    st.subheader("2. Quiz Parameters")
    
    num_questions = st.number_input(
        "Number of questions:", 
        min_value=1, 
        max_value=20, 
        value=5, 
        step=1
    )
    
    arrange_mode = "By Session"
    if len(selected_session_titles) >= 2:
        arrange_mode = st.radio(
            "Question Arrangement:",
            options=["By Session", "Shuffle"],
            help="'By Session' groups questions sequentially by lecture. 'Shuffle' mixes them up."
        )
        
    generate_btn = st.button("Generate Practice Quiz", type="primary")

with col2:
    st.subheader("3. Generated Quiz Output")
    
    if generate_btn:
        if not selected_session_titles:
            st.error("Please select at least one lecture session.")
        else:
            with st.spinner("Analyzing full lecture slide decks and generating NBME-grade quiz..."):
                combined_content = ""
                combined_styles = ""
                
                k = len(selected_session_titles)
                base_quota = num_questions // k
                remainder = num_questions % k
                
                for idx, title in enumerate(selected_session_titles):
                    quota = base_quota + (1 if idx < remainder else 0)
                    sess = sessions_dict[title]
                    
                    # Passing 100% of slide text without truncation
                    slides_text = sess.get("slides", "")
                    
                    combined_content += f"\n\n=========================================\n"
                    combined_content += f"SESSION: '{title}' (Target Questions: {quota})\n"
                    combined_content += f"=========================================\n"
                    combined_content += slides_text
                    
                    sess_style = sess.get("style_profile")
                    if sess_style:
                        combined_styles += f"\n--- Style Profile for {title} ---\n" + sess_style
                    elif global_course_style:
                        combined_styles += f"\n--- Course-Wide Style Profile for {title} ---\n" + global_course_style

                prompt = f"""
                You are an expert medical school professor writing board-style practice questions for {selected_course}.
                
                --- CRITICAL GROUNDING RULES ---
                1. STRICT SCOPE: All questions, choices, and distractors MUST be grounded STRICTLY in facts explicitly stated in the provided lecture slides. Do NOT test on external information.
                2. OBJECTIVES ALIGNMENT: Locate the "Session/Lecture Learning Objectives" (usually on early slides) for each session. Ensure every question directly tests a stated learning objective.
                3. SINGLE SESSION ASSIGNMENT: Each question corresponds to EXACTLY ONE lecture session.
                
                --- SESSION CONTENT & TARGET QUESTION DISTRIBUTION ---
                {combined_content}

                --- PROFESSOR STYLE PROFILE ---
                {combined_styles if combined_styles else "Use standard NBME clinical vignette style with 4-5 options."}

                --- ARRANGEMENT & FORMATTING ---
                * Total Questions to generate: {num_questions}.
                * Arrangement Mode requested: '{arrange_mode}'.
                  - If 'By Session': Group all questions for Session 1 together, then Session 2, etc.
                  - If 'Shuffle': Interleave and shuffle the questions across the selected sessions randomly.
                
                Format your output clearly into two main sections:
                
                SECTION 1: QUESTIONS
                For each question, explicitly state the corresponding session title before the question stem.
                Format:
                Question [Number] ([Session Title])
                [Vignette / Stem]
                A) ...
                B) ...
                C) ...
                D) ...
                E) ...

                SECTION 2: ANSWER KEY & RATIONALES
                For each question:
                - Correct Answer
                - Detailed Rationale explaining why the correct option is right based on slide facts, and why distractors are wrong.
                - Exact Slide/Page Citation from the session slides.
                """

                try:
                    output_container = st.empty()
                    full_text = ""
                    response = model.generate_content(prompt, stream=True)
                    for chunk in response:
                        if chunk.text:
                            full_text += chunk.text
                            output_container.text_area("Copyable Quiz Output:", value=full_text, height=600)
                except Exception as e:
                    st.error(f"Error generating questions: {e}")
