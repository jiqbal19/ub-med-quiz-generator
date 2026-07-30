import streamlit as st
import pypdf
import requests
import random

st.set_page_config(page_title="Faculty Studio", page_icon="👨‍🏫", layout="wide")

BIN_ID = st.secrets.get("JSONBIN_BIN_ID", "")
JSONBIN_KEY = st.secrets.get("JSONBIN_API_KEY", "")
DEV_OVERRIDE = "1901"

if not BIN_ID or not JSONBIN_KEY:
    st.error("🔑 Database Credentials missing in Streamlit Secrets!")
    st.stop()

def load_cloud_data():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json().get("record", {})
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

def extract_text_from_pdf(pdf_file):
    pdf_reader = pypdf.PdfReader(pdf_file)
    text = ""
    for page_num, page in enumerate(pdf_reader.pages, start=1):
        extracted = page.extract_text()
        if extracted:
            text += f"\n--- Slide/Page {page_num} ---\n" + extracted
    return text

data = load_cloud_data()

if "authenticated_course" not in st.session_state:
    st.session_state.authenticated_course = None
if "show_delete_course_confirm" not in st.session_state:
    st.session_state.show_delete_course_confirm = False

st.title("👨‍🏫 Faculty Studio Portal")

if not st.session_state.authenticated_course:
    st.caption("Manage course sessions, upload slide decks, and set style exemplars.")
    
    tab1, tab2 = st.tabs(["🔒 Enter Existing Course", "➕ Create New Course"])
    
    with tab1:
        if not data:
            st.info("No courses created yet. Switch to 'Create New Course' to get started.")
        else:
            selected_course = st.selectbox("Select Course:", options=list(data.keys()))
            entered_code = st.text_input("Enter 4-Digit Passcode:", type="password")
            
            if st.button("Enter Studio", type="primary"):
                stored_code = str(data[selected_course].get("passcode"))
                if entered_code == stored_code or entered_code == DEV_OVERRIDE:
                    st.session_state.authenticated_course = selected_course
                    st.session_state.show_delete_course_confirm = False
                    st.rerun()
                else:
                    st.error("Incorrect passcode. Access denied.")

    with tab2:
        new_course_name = st.text_input("Course Name (e.g., 'Microbiology Fall 2026')")
        if st.button("Generate Course Workspace", type="primary"):
            if not new_course_name.strip():
                st.warning("Please enter a course name.")
            elif new_course_name in data:
                st.warning("A course with this name already exists.")
            else:
                generated_passcode = str(random.randint(1000, 9999))
                data[new_course_name] = {
                    "passcode": generated_passcode,
                    "global_style_pqs": "",
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
    t_add, t_manage = st.tabs(["➕ Add New Session", "🛠️ View/Edit Published Sessions"])
    
    with t_add:
        session_title = st.text_input("Session Title (e.g., 'Lecture 1: Gram-Positive Cocci')")
        slides_file = st.file_uploader("Upload Lecture Slides (PDF)", type=["pdf"], key="add_slides")
        pqs_file = st.file_uploader("Upload Practice Questions/Answers (PDF - Optional)", type=["pdf"], key="add_pqs")
        
        if st.button("Save & Publish Session", type="primary"):
            if not session_title:
                st.warning("Please enter a session title.")
            elif not slides_file:
                st.warning("Please upload a slide PDF.")
            else:
                with st.spinner("Parsing PDF and saving to cloud..."):
                    slides_text = extract_text_from_pdf(slides_file)
                    pqs_text = extract_text_from_pdf(pqs_file) if pqs_file else ""
                    
                    course_data["sessions"][session_title] = {
                        "slides": slides_text,
                        "pqs": pqs_text
                    }
                    
                    if pqs_text:
                        course_data["global_style_pqs"] += f"\n--- {session_title} Exemplars ---\n" + pqs_text
                        
                    save_cloud_data(data)
                    st.success(f"Published and synced '{session_title}' live!")

    with t_manage:
        sessions = course_data.get("sessions", {})
        if not sessions:
            st.info("No published sessions in this course yet.")
        else:
            for s_title in list(sessions.keys()):
                with st.expander(f"📖 {s_title}"):
                    has_pqs = bool(sessions[s_title].get("pqs"))
                    st.write(f"**Status:** {'🟢 Custom PQs Attached' if has_pqs else '🟡 Using Global Style Fallback'}")
                    st.write(f"**Slide Text Length:** {len(sessions[s_title]['slides'])} characters")
                    
                    if st.button(f"🗑️ Delete '{s_title}'", key=f"del_{s_title}"):
                        del course_data["sessions"][s_title]
                        save_cloud_data(data)
                        st.success(f"Deleted '{s_title}'.")
                        st.rerun()
