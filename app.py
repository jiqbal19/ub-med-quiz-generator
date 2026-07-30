import streamlit as st
import google.generativeai as genai
import json
import os

st.set_page_config(page_title="UB Med Practice Generator", page_icon="🩺", layout="wide")

# Persistent Storage File Path
DATA_FILE = "courses_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

data = load_data()

# API Setup
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("🔑 Gemini API Key missing! Add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- STUDENT QUESTION GENERATOR ---
st.title("🎓 Student Practice Question Generator")
st.caption("Select your course and lecture sessions to generate board-style practice questions.")

if not data:
    st.info("No courses are currently available. Please check back after faculty publish sessions.")
    st.stop()

# 1. Course Selection
selected_course = st.selectbox("Select Course:", options=list(data.keys()))

course_info = data[selected_course]
sessions = course_info.get("sessions", {})

if not sessions:
    st.warning(f"No lecture sessions available for {selected_course} yet.")
    st.stop()

st.markdown("---")
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Quiz Parameters")
    selected_sessions = st.multiselect(
        "Select Session(s) to practice:",
        options=list(sessions.keys())
    )
    
    num_questions = st.slider("Number of questions:", min_value=1, max_value=20, value=5)
    generate_btn = st.button("Generate Practice Quiz", type="primary")

with col2:
    st.subheader("2. Generated Quiz Output")
    
    if generate_btn:
        if not selected_sessions:
            st.error("Please select at least one lecture session.")
        else:
            with st.spinner("Analyzing lecture material and drafting questions..."):
                combined_slides = ""
                combined_pqs = ""
                
                for title in selected_sessions:
                    sess = sessions[title]
                    combined_slides += f"\n=== SESSION: {title} ===\n" + sess["slides"]
                    if sess.get("pqs"):
                        combined_pqs += f"\n=== PQs for {title} ===\n" + sess["pqs"]
                
                style_context = combined_pqs if combined_pqs else course_info.get("global_style_pqs", "")
                
                prompt = f"""
                You are an expert medical school professor teaching {selected_course}. Your task is to generate {num_questions} board-style multiple-choice practice questions grounded STRICTLY in the provided lecture slides.

                --- LECTURE SLIDE CONTENT ---
                {combined_slides}

                --- PROFESSOR'S QUESTION WRITING STYLE EXEMPLARS ---
                {style_context if style_context else "Use standard NBME clinical vignette style with 4-5 options."}

                --- REQUIREMENTS ---
                1. Write {num_questions} multiple-choice questions matching the professor's tone, vignette length, and distractor style.
                2. Do NOT hallucinate medical facts outside the provided slide content.
                3. Format your response clearly into two sections:
                   SECTION 1: QUESTIONS (Question stem, choices A-E)
                   SECTION 2: ANSWER KEY & RATIONALES (Correct answer, detailed rationale, and exact Slide/Page citation).
                """

                try:
                    response = model.generate_content(prompt)
                    st.text_area("Copyable Quiz Output:", value=response.text, height=500)
                except Exception as e:
                    st.error(f"Error generating questions: {e}")
