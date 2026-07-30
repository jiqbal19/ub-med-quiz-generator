import streamlit as st
from google import genai
import requests
import time
import tempfile
import os
from datetime import datetime

st.set_page_config(page_title="UB Med Practice Generator", page_icon="🩺", layout="wide")

GEMINI_KEY = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
BIN_ID = str(st.secrets.get("JSONBIN_BIN_ID", "")).strip()
JSONBIN_KEY = str(st.secrets.get("JSONBIN_API_KEY", "")).strip()

if not GEMINI_KEY or GEMINI_KEY == "None":
    st.error("🔑 `GEMINI_API_KEY` is missing in your Streamlit Secrets dashboard!")
    st.stop()

if not BIN_ID or not JSONBIN_KEY:
    st.error("🔑 JSONBin credentials missing in Streamlit Secrets!")
    st.stop()

# Initialize Google GenAI client
client = genai.Client(api_key=GEMINI_KEY)

# Active production models for google-genai SDK
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ["gemini-2.5-pro", "gemini-1.5-flash"]

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
st.caption("Select your course and lecture sessions to generate practice questions modeled after your faculty's in-house exam style.")

data = load_cloud_data()

if not data:
    st.info("No active courses are currently available. Please check back after faculty publish a course.")
    st.stop()

selected_course = st.selectbox(
    "Select Course:", 
    options=list(data.keys()),
    disabled=st.session_state.get("is_generating", False)
)
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

if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

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
        if st.checkbox(
            display_label, 
            key=f"cb_{selected_course}_{title}",
            disabled=st.session_state.is_generating
        ):
            selected_session_titles.append(title)
            
    st.markdown("---")
    st.subheader("2. Quiz Parameters")
    
    num_questions = st.number_input(
        "Number of questions:", 
        min_value=1, 
        max_value=20, 
        value=5, 
        step=1,
        disabled=st.session_state.is_generating
    )
    
    arrange_mode = "By Session"
    if len(selected_session_titles) >= 2:
        arrange_mode = st.radio(
            "Question Arrangement:",
            options=["By Session", "Shuffle"],
            help="'By Session' groups questions sequentially by lecture. 'Shuffle' mixes them up.",
            disabled=st.session_state.is_generating
        )
    
    st.markdown("---")
    
    if not st.session_state.is_generating:
        if st.button("🚀 Generate Practice Quiz", type="primary"):
            if not selected_session_titles:
                st.error("Please select at least one lecture session.")
            else:
                st.session_state.is_generating = True
                st.rerun()
    else:
        if st.button("🛑 Cancel & Reset Quiz", type="primary"):
            st.session_state.is_generating = False
            st.warning("Generation cancelled.")
            st.rerun()

with col2:
    st.subheader("3. Generated Quiz Output")
    
    if st.session_state.is_generating:
        # Prompt only on tab close or page refresh
        st.components.v1.html("""
            <script>
            window.addEventListener('beforeunload', function (e) {
                e.preventDefault();
                e.returnValue = '';
            });
            </script>
        """, height=0)

        status_box = st.empty()
        progress_bar = st.progress(0)
        output_container = st.empty()
        
        status_box.info("⚡ Preparing full slide decks for AI context...")
        progress_bar.progress(15)
        
        uploaded_files = []
        combined_styles = ""
        session_instructions = ""
        
        k = len(selected_session_titles)
        base_quota = num_questions // k
        remainder = num_questions % k
        
        try:
            for idx, title in enumerate(selected_session_titles):
                quota = base_quota + (1 if idx < remainder else 0)
                sess = sessions_dict[title]
                slides_text = sess.get("slides", "")
                
                with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as temp_file:
                    temp_file.write(f"FULL LECTURE SLIDES FOR SESSION: '{title}'\n\n" + slides_text)
                    temp_path = temp_file.name
                
                g_file = client.files.upload(file=temp_path)
                uploaded_files.append(g_file)
                os.remove(temp_path)
                
                session_instructions += f"\n- Session '{title}': Generate exactly {quota} question(s)."
                
                sess_style = sess.get("style_profile")
                if sess_style:
                    combined_styles += f"\n--- Faculty Writing Style Guidelines for {title} ---\n" + sess_style
                elif global_course_style:
                    combined_styles += f"\n--- Course-Wide Faculty Writing Style Guidelines ---\n" + global_course_style

            progress_bar.progress(40)
            status_box.info("🧠 Analyzing 100% of slide contents & matching faculty style...")

            prompt = f"""
            You are a medical school faculty member writing in-house exam practice questions for students enrolled in {selected_course}.
            
            --- CRITICAL GROUNDING RULES ---
            1. STRICT SCOPE: All questions, options, and distractors MUST be grounded STRICTLY in facts explicitly stated in the provided lecture slide documents. Read through all slides completely.
            2. OBJECTIVES ALIGNMENT: Locate the "Session/Lecture Learning Objectives" (usually on early slides) for each session document. Ensure every question directly tests a stated session learning objective.
            3. SINGLE SESSION ASSIGNMENT: Each question corresponds to EXACTLY ONE lecture session document.
            
            --- TARGET QUESTION DISTRIBUTION PER SESSION ---
            {session_instructions}

            --- IN-HOUSE FACULTY QUESTION WRITING STYLE ---
            Emulate the exact tone, vignette structure, stem phrasing, and distractor style outlined below:
            {combined_styles if combined_styles else "Write clear, high-yield in-house medical school exam questions based strictly on the slides."}

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

            contents_payload = uploaded_files + [prompt]

            response = None
            models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
            
            for target_model in models_to_try:
                try:
                    response = client.models.generate_content_stream(
                        model=target_model,
                        contents=contents_payload
                    )
                    break
                except Exception as model_err:
                    if "503" in str(model_err) or "UNAVAILABLE" in str(model_err) or "404" in str(model_err):
                        status_box.warning(f"⚠️ Model '{target_model}' busy or unavailable. Trying alternative engine...")
                        time.sleep(1)
                        continue
                    else:
                        raise model_err

            if not response:
                raise Exception("Google API endpoints are currently experiencing high demand. Please try again in a few moments.")

            progress_bar.progress(60)
            status_box.info("✍️ Live Streaming: Writing questions & rationales below...")
            
            full_text = ""
            chunk_count = 0
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    chunk_count += 1
                    current_prog = min(60 + (chunk_count * 2), 98)
                    progress_bar.progress(current_prog)
                    output_container.text_area("Copyable Quiz Output:", value=full_text, height=600)

            for g_f in uploaded_files:
                try:
                    client.files.delete(name=g_f.name)
                except Exception:
                    pass

            progress_bar.progress(100)
            status_box.success("🎉 Quiz Generation Complete!")
            time.sleep(1)
            progress_bar.empty()
            
            st.session_state.is_generating = False
            st.rerun()
            
        except Exception as e:
            for g_f in uploaded_files:
                try:
                    client.files.delete(name=g_f.name)
                except Exception:
                    pass
                    
            st.session_state.is_generating = False
            status_box.empty()
            progress_bar.empty()
            st.error(f"Error generating questions: {e}")
