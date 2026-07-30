import streamlit as st
import google.generativeai as genai
import pypdf
import json

# Page Configuration
st.set_page_config(page_title="UB Med Practice Generator", page_icon="🩺", layout="wide")

# Initialize Session State Variables
if "sessions" not in st.session_state:
    st.session_state.sessions = {}  # Format: {session_title: {"slides_text": "", "pqs_text": ""}}
if "global_style_pqs" not in st.session_state:
    st.session_state.global_style_pqs = ""

# API Key Setup
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("🔑 Gemini API Key missing! Please add GEMINI_API_KEY to your Streamlit App Secrets.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# Helper Function: Read PDF Text
def extract_text_from_pdf(pdf_file):
    pdf_reader = pypdf.PdfReader(pdf_file)
    text = ""
    for page_num, page in enumerate(pdf_reader.pages, start=1):
        extracted = page.extract_text()
        if extracted:
            text += f"\n--- Slide/Page {page_num} ---\n" + extracted
    return text

# Navigation Sidebar
st.sidebar.title("Jacobs School Med-Quiz")
user_role = st.sidebar.radio("Select View:", ["🎓 Student Portal", "👨‍🏫 Faculty Studio"])

# ==========================================
# 👨‍🏫 FACULTY STUDIO (Course & Session Management)
# ==========================================
if user_role == "👨‍🏫 Faculty Studio":
    st.title("👨‍🏫 Faculty Session Builder")
    st.caption("Create lecture sessions, upload slide decks, and set style exemplars for your course.")

    with st.expander("➕ Create a New Lecture Session", expanded=True):
        session_title = st.text_input("Session Title (e.g., 'Lecture 1: Gram-Positive Cocci')")
        slides_file = st.file_uploader("Upload Lecture Slides (PDF)", type=["pdf"], key="slides")
        pqs_file = st.file_uploader("Upload Practice Questions/Answers for this Session (PDF - Optional)", type=["pdf"], key="pqs")
        
        if st.button("Save & Publish Session", type="primary"):
            if not session_title:
                st.warning("Please enter a session title.")
            elif not slides_file:
                st.warning("Please upload a lecture slide PDF.")
            else:
                with st.spinner("Processing PDF content..."):
                    slides_text = extract_text_from_pdf(slides_file)
                    pqs_text = extract_text_from_pdf(pqs_file) if pqs_file else ""
                    
                    # Store session data
                    st.session_state.sessions[session_title] = {
                        "slides": slides_text,
                        "pqs": pqs_text
                    }
                    
                    # Update global style fallback if PQs were provided
                    if pqs_text:
                        st.session_state.global_style_pqs += f"\n--- {session_title} Exemplars ---\n" + pqs_text
                        
                st.success(f"Successfully published '{session_title}'!")

    st.markdown("---")
    st.subheader("📚 Currently Published Sessions")
    if not st.session_state.sessions:
        st.info("No active sessions created yet.")
    else:
        for title in st.session_state.sessions:
            has_pqs = bool(st.session_state.sessions[title]["pqs"])
            status = "🟢 Custom PQs Included" if has_pqs else "🟡 Using Global Style Fallback"
            st.write(f"• **{title}** — {status}")

# ==========================================
# 🎓 STUDENT PORTAL (Quiz Generation)
# ==========================================
else:
    st.title("🎓 Practice Question Generator")
    st.caption("Select your lecture sessions to generate board-style practice questions with slide citations.")

    if not st.session_state.sessions:
        st.warning("No sessions are currently available. Please switch to the Faculty Studio to add a session first!")
    else:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("1. Quiz Parameters")
            selected_sessions = st.multiselect(
                "Select Session(s) to practice:",
                options=list(st.session_state.sessions.keys())
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
                        # Aggregate selected content and determine style context
                        combined_slides = ""
                        combined_pqs = ""
                        
                        for title in selected_sessions:
                            combined_slides += f"\n=== SESSION: {title} ===\n" + st.session_state.sessions[title]["slides"]
                            if st.session_state.sessions[title]["pqs"]:
                                combined_pqs += f"\n=== PQs for {title} ===\n" + st.session_state.sessions[title]["pqs"]
                        
                        # Fallback to global professor PQs if this session lacks specific PQs
                        style_context = combined_pqs if combined_pqs else st.session_state.global_style_pqs
                        
                        # Build standard prompt
                        prompt = f"""
                        You are an expert medical school professor. Your task is to generate {num_questions} board-style multiple-choice practice questions grounded STRICTLY in the provided lecture slides.

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
