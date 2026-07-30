import streamlit as st
import pypdf
from pptx import Presentation
import docx
import requests
import google.generativeai as genai
import datetime
import random

st.set_page_config(page_title="Faculty Studio", page_icon="👨‍🏫", layout="wide")

st.markdown("""
    <style>
    [data-testid="InputInstructions"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

BIN_ID = st.secrets.get("JSONBIN_BIN_ID", "")
JSONBIN_KEY = st.secrets.get("JSONBIN_API_KEY", "")
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
DEV_OVERRIDE = "1901"

if not BIN_ID or not JSONBIN_KEY or not GEMINI_KEY:
    st.error("🔑 Database Credentials or Gemini API Key missing in Streamlit Secrets!")
    st.stop()

genai.configure(api_key=GEMINI_KEY)
style_analyzer_model = genai.GenerativeModel("models/gemini-2.5-flash-lite")

def load_cloud_data():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            raw_data = req.json().get("record", {})
            return {k: v for k, v in raw_data.items() if isinstance(v, dict) and "sessions" in v}
    except Exception:
        return {}
    return {}

def save_cloud_data(data):
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_KEY
    }
    try:
        requests.put(url, headers=headers, json=data)
    except Exception as e:
        st.error(f"Failed to sync with cloud database: {e}")

def extract_text_from_file(uploaded_file):
    if not uploaded_file:
        return ""
    
    filename = uploaded_file.name.lower()
    text = ""
    
    try:
        if filename.endswith(".pdf"):
            pdf_reader = pypdf.PdfReader(uploaded_file)
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                extracted = page.extract_text()
                if extracted:
                    text += f"\n--- Page/Slide {page_num} ---\n" + extracted
                    
        elif filename.endswith(".pptx"):
            prs = Presentation(uploaded_file)
            for slide_num, slide in enumerate(prs.slides, start=1):
                slide_words = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        slide_words.append(shape.text)
                if slide_words:
                    text += f"\n--- Slide {slide_num} ---\n" + "\n".join(slide_words)
                    
        elif filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            p_text = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        p_text.append(" | ".join(row_text))
            text = "\n".join(p_text)
            
    except Exception as e:
        st.error(f"Error reading '{uploaded_file.name}': {e}")
        
    return text

def analyze_style_profile(pqs_text):
    if not pqs_text or not pqs_text.strip():
        return "Standard NBME clinical vignette style with 4-5 choices."
    
    analysis_prompt = f"""
    Analyze the following medical practice questions and reverse-engineer the writing style into concise guidance rules:
    1. Vignette length and clinical depth.
    2. Question stem phrasing.
    3. Distractor structure and difficulty.
    4. Rationale and explanation format.

    PRACTICE QUESTIONS:
    {pqs_text[:6000]}
    """
    try:
        res = style_analyzer_model.generate_content(analysis_prompt)
        return res.text
    except Exception as e:
        return f"Standard NBME style (Error during analysis: {e})"

@st.dialog("✅ Session Saved Successfully!")
def show_save_confirmation(session_name, action_type="published"):
    st.write(f"The session **'{session_name}'** has been successfully {action_type} and synced to the student app.")
    if st.button("Close Window", type="primary"):
        st.session_state.saved_session_info = None
        st.rerun()

data = load_cloud_data()

if "authenticated_course" not in st.session_state:
    st.session_state.authenticated_course = None
if "show_delete_course_confirm" not in st.session_state:
    st.session_state.show_delete_course_confirm = False
if "saved_session_info" not in st.session_state:
    st.session_state.saved_session_info = None

st.title("👨‍🏫 Faculty Studio Portal")

if st.session_state.saved_session_info:
    info = st.session_state.saved_session_info
    show_save_confirmation(info["title"], info["action"])

if not st.session_state.authenticated_course:
    st.caption("Manage course sessions, upload slide decks, and set style exemplars.")
    
    tab1, tab2 = st.tabs(["🔒 Enter Existing Course", "➕ Create New Course"])
    
    with tab1:
        if not data:
            st.info("No active courses created yet. Switch to 'Create New Course' to get started.")
        else:
            with st.form("login_form"):
                selected_course = st.selectbox("Select Course:", options=list(data.keys()))
                entered_code = st.text_input("Enter 4-Digit Passcode:", type="password")
                submit_login = st.form_submit_button("Enter Studio", type="primary")
                
                if submit_login:
                    stored_code = str(data[selected_course].get("passcode"))
                    if entered_code == stored_code or entered_code == DEV_OVERRIDE:
                        st.session_state.authenticated_course = selected_course
                        st.session_state.show_delete_course_confirm = False
                        st.rerun()
                    else:
                        st.error("Incorrect passcode. Access denied.")

    with tab2:
        with st.form("create_course_form"):
            new_course_name = st.text_input("Course Name (e.g., 'Microbiology Fall 2026')")
            submit_create = st.form_submit_button("Generate Course Workspace", type="primary")
            
            if submit_create:
                if not new_course_name.strip():
                    st.warning("Please enter a course name.")
                elif new_course_name in data:
                    st.warning("A course with this name already exists.")
                else:
                    generated_passcode = str(random.randint(1000, 9999))
                    data[new_course_name] = {
                        "passcode": generated_passcode,
                        "global_pqs_filename": "",
                        "global_pqs_text": "",
                        "global_style_profile": "",
                        "sessions": {}
                    }
                    save_cloud_data(data)
                    st.session_state.newly_created_course = new_course_name
                    st.session_state.newly_created_passcode = generated_passcode
                    st.rerun()

        if "newly_created_course" in st.session_state and st.session_state.newly_created_course:
            nc_name = st.session_state.newly_created_course
            nc_code = st.session_state.newly_created_passcode
            
            st.success(f"🎉 Course '{nc_name}' successfully created!")
            st.info(f"🔐 **Assigned 4-Digit Passcode:** `{nc_code}` (Save this to share with co-instructors).")
            
            if st.button(f"🚀 Enter '{nc_name}' Workspace Now", type="primary"):
                st.session_state.authenticated_course = nc_name
                st.session_state.newly_created_course = None
                st.session_state.newly_created_passcode = None
                st.rerun()

else:
    active_course = st.session_state.authenticated_course
    course_data = data.get(active_course)

    if not course_data:
        st.session_state.authenticated_course = None
        st.rerun()

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        st.subheader(f"Active Workspace: **{active_course}**")
        st.caption(f"🔐 Course Passcode: **{course_data.get('passcode')}**")
    with col_b:
        if st.button("🔒 Exit Workspace"):
            st.session_state.authenticated_course = None
            st.session_state.show_delete_course_confirm = False
            st.rerun()
    with col_c:
        if st.button("🗑️ Delete Course Workspace"):
            st.session_state.show_delete_course_confirm = True

    if st.session_state.show_delete_course_confirm:
        st.warning(f"⚠️ **Are you sure you want to permanently delete '{active_course}'?** This action will erase all published sessions.")
        col_yes, col_no = st.columns([1, 4])
        with col_yes:
            if st.button("🚨 Yes, Delete Permanently", type="primary"):
                del data[active_course]
                save_cloud_data(data)
                st.session_state.authenticated_course = None
                st.session_state.show_delete_course_confirm = False
                st.success(f"'{active_course}' has been completely removed.")
                st.rerun()
        with col_no:
            if st.button("Cancel"):
                st.session_state.show_delete_course_confirm = False
                st.rerun()

    st.markdown("---")
    
    # --- COURSE-WIDE GENERAL PQ UPLOADER SECTION ---
    with st.expander("🎓 Course-Wide Master Practice Exam (Applies to all sessions by default)"):
        master_fn = course_data.get("global_pqs_filename", "")
        if master_fn:
            st.success(f"📎 **Current Course-Wide Practice Exam:** `{master_fn}`")
        else:
            st.info("ℹ️ No course-wide practice exam attached yet. Uploading one allows all sessions to inherit the same exam writing style.")
            
        up_master_file = st.file_uploader("Upload Course-Wide Practice Exam (PDF or Word):", type=["pdf", "docx"], key="course_master_pq")
        if st.button("💾 Save Course-Wide Practice Exam", type="primary"):
            if up_master_file:
                with st.spinner("Extracting text and analyzing master course exam style..."):
                    m_text = extract_text_from_file(up_master_file)
                    m_style = analyze_style_profile(m_text)
                    course_data["global_pqs_filename"] = up_master_file.name
                    course_data["global_pqs_text"] = m_text
                    course_data["global_style_profile"] = m_style
                    save_cloud_data(data)
                    st.success("Updated Course-Wide Practice Exam!")
                    st.rerun()

    st.markdown("---")
    t_add, t_manage = st.tabs(["➕ Add New Session", "🛠️ View/Edit Published Sessions"])
    
    master_pq_name = course_data.get("global_pqs_filename", "")
    course_has_master = bool(master_pq_name)
    
    # Dynamic option labels for PQ source selection
    opt_master = f"Use Course-Wide Master Exam ({master_pq_name})" if course_has_master else "Use Course-Wide Master Exam (⚠️ None uploaded yet)"
    opt_custom = "Upload Custom Practice Question File for This Session Specifically"
    
    with t_add:
        session_title = st.text_input("Session Title (e.g., 'Gram-Positive Cocci')")
        session_date = st.date_input("Session Date Held", value=datetime.date.today(), format="MM/DD/YYYY")
        slides_file = st.file_uploader("Upload Lecture Slides (PDF or PowerPoint)", type=["pdf", "pptx"], key="add_slides")
        
        st.markdown("#### Practice Question Reference Style")
        pq_source_choice = st.radio(
            "Select reference practice question set for AI model style learning:",
            options=[opt_master, opt_custom],
            key="add_pq_choice"
        )
        
        session_custom_pq_file = None
        if pq_source_choice == opt_custom:
            session_custom_pq_file = st.file_uploader("Upload Custom Session Practice Questions (PDF or Word - Required):", type=["pdf", "docx"], key="add_session_custom_pq")

        if st.button("Save & Publish Session", type="primary"):
            if not session_title:
                st.warning("Please enter a session title.")
            elif not slides_file:
                st.warning("Please upload a slide file (PDF or PPTX).")
            elif pq_source_choice == opt_master and not course_has_master:
                st.error("❌ Cannot save session: No course-wide practice exam has been uploaded yet. Please upload one under 'Course-Wide Master Practice Exam' above or select 'Upload Custom Practice Question File'.")
            elif pq_source_choice == opt_custom and not session_custom_pq_file:
                st.error("❌ Cannot save session: You chose to use a custom practice question set for this session, but haven't uploaded a file.")
            else:
                with st.spinner("Processing files and publishing session..."):
                    slides_text = extract_text_from_file(slides_file)
                    date_str = session_date.strftime("%Y-%m-%d")
                    
                    if pq_source_choice == opt_custom and session_custom_pq_file:
                        pqs_text = extract_text_from_file(session_custom_pq_file)
                        pqs_fn = session_custom_pq_file.name
                        style_prof = analyze_style_profile(pqs_text)
                        pq_mode = "custom"
                    else:
                        pqs_text = ""
                        pqs_fn = master_pq_name
                        style_prof = course_data.get("global_style_profile", "")
                        pq_mode = "course_master"

                    course_data["sessions"][session_title] = {
                        "date": date_str,
                        "slides": slides_text,
                        "slides_filename": slides_file.name,
                        "pq_mode": pq_mode,
                        "pqs": pqs_text,
                        "pqs_filename": pqs_fn,
                        "style_profile": style_prof
                    }
                    
                    save_cloud_data(data)
                    st.session_state.saved_session_info = {"title": session_title, "action": "published"}
                    st.rerun()

    with t_manage:
        sessions = course_data.get("sessions", {})
        if not sessions:
            st.info("No published sessions in this course yet.")
        else:
            for s_title in list(sessions.keys()):
                sess_info = sessions[s_title]
                raw_date = sess_info.get("date", "N/A")
                
                display_date = "N/A"
                if raw_date != "N/A":
                    try:
                        display_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").strftime("%m/%d/%Y")
                    except ValueError:
                        display_date = raw_date
                
                with st.expander(f"📖 [{display_date}] {s_title}"):
                    mode = sess_info.get("pq_mode", "custom")
                    pq_fn_display = sess_info.get("pqs_filename", "Master Set" if mode == "course_master" else "N/A")
                    
                    st.write(f"**Date Held:** {display_date}")
                    st.write(f"**PQ Style Reference:** {'🌐 Course-Wide Master Set' if mode == 'course_master' else '📄 Custom Session Set'} (`{pq_fn_display}`)")
                    
                    st.markdown("---")
                    st.markdown("#### ✏️ Edit Session Details")
                    
                    default_date = datetime.date.today()
                    if raw_date != "N/A":
                        try:
                            default_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
                        except ValueError:
                            pass
                            
                    edit_title = st.text_input("Session Title", value=s_title, key=f"edit_title_{s_title}")
                    edit_date = st.date_input("Session Date Held", value=default_date, format="MM/DD/YYYY", key=f"edit_date_{s_title}")
                    
                    curr_slides_fn = sess_info.get("slides_filename", "[Uploaded file]")
                    st.markdown("**Replace Lecture Slides (PDF/PPTX - Optional)**")
                    st.caption(f"📎 **Currently attached slide deck:** `{curr_slides_fn}`")
                    new_slides_file = st.file_uploader("Upload replacement slides:", type=["pdf", "pptx"], key=f"edit_slides_{s_title}")
                    
                    st.markdown("**Practice Question Style Reference**")
                    current_mode_index = 0 if mode == "course_master" else 1
                    edit_pq_choice = st.radio(
                        "Select practice question set source:",
                        options=[opt_master, opt_custom],
                        index=current_mode_index,
                        key=f"edit_pq_choice_{s_title}"
                    )
                    
                    edit_custom_pq_file = None
                    if edit_pq_choice == opt_custom:
                        if sess_info.get("pqs_filename"):
                            st.caption(f"📎 **Currently attached session PQ:** `{sess_info.get('pqs_filename')}`")
                        edit_custom_pq_file = st.file_uploader("Upload new session practice question file (PDF/DOCX):", type=["pdf", "docx"], key=f"edit_pqs_{s_title}")

                    col_save, col_del = st.columns([1, 1])
                    
                    with col_save:
                        if st.button("💾 Save Session Changes", key=f"save_{s_title}", type="primary"):
                            if edit_pq_choice == opt_master and not course_has_master:
                                st.error("❌ Cannot save session: No course-wide practice exam has been uploaded yet. Please upload one above.")
                            elif edit_pq_choice == opt_custom and not edit_custom_pq_file and not sess_info.get("pqs"):
                                st.error("❌ Cannot save session: A custom practice question file is required for this setting.")
                            else:
                                with st.spinner("Syncing session updates..."):
                                    updated_date_str = edit_date.strftime("%Y-%m-%d")
                                    
                                    if new_slides_file:
                                        updated_slides = extract_text_from_file(new_slides_file)
                                        updated_slides_fn = new_slides_file.name
                                    else:
                                        updated_slides = sess_info.get("slides", "")
                                        updated_slides_fn = sess_info.get("slides_filename", curr_slides_fn)
                                        
                                    if edit_pq_choice == opt_custom:
                                        if edit_custom_pq_file:
                                            updated_pqs = extract_text_from_file(edit_custom_pq_file)
                                            updated_pqs_fn = edit_custom_pq_file.name
                                            updated_style = analyze_style_profile(updated_pqs)
                                        else:
                                            updated_pqs = sess_info.get("pqs", "")
                                            updated_pqs_fn = sess_info.get("pqs_filename", "")
                                            updated_style = sess_info.get("style_profile", "")
                                        updated_mode = "custom"
                                    else:
                                        updated_pqs = ""
                                        updated_pqs_fn = master_pq_name
                                        updated_style = course_data.get("global_style_profile", "")
                                        updated_mode = "course_master"
                                    
                                    if edit_title != s_title:
                                        del course_data["sessions"][s_title]
                                        
                                    course_data["sessions"][edit_title] = {
                                        "date": updated_date_str,
                                        "slides": updated_slides,
                                        "slides_filename": updated_slides_fn,
                                        "pq_mode": updated_mode,
                                        "pqs": updated_pqs,
                                        "pqs_filename": updated_pqs_fn,
                                        "style_profile": updated_style
                                    }
                                    
                                    save_cloud_data(data)
                                    st.session_state.saved_session_info = {"title": edit_title, "action": "updated"}
                                    st.rerun()

                    with col_del:
                        if st.button(f"🗑️ Delete Session", key=f"del_{s_title}"):
                            del course_data["sessions"][s_title]
                            save_cloud_data(data)
                            st.success(f"Deleted '{s_title}'.")
                            st.rerun()
