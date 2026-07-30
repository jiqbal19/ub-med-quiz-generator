import streamlit as st
import requests

st.set_page_config(page_title="UB Med Practice Generator - Faculty Portal", page_icon="🩺", layout="wide")

BIN_ID = str(st.secrets.get("JSONBIN_BIN_ID", "")).strip()
JSONBIN_KEY = str(st.secrets.get("JSONBIN_API_KEY", "")).strip()

if not BIN_ID or not JSONBIN_KEY:
    st.error("🔑 JSONBin credentials missing in Streamlit Secrets!")
    st.stop()

def load_cloud_data():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json().get("record", {})
    except Exception as e:
        st.error(f"Error reading database: {e}")
    return {}

def save_cloud_data(data):
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_KEY
    }
    try:
        req = requests.put(url, headers=headers, json=data)
        if req.status_code == 200:
            return True
        else:
            st.error(f"Save failed ({req.status_code}): {req.text}")
            return False
    except Exception as e:
        st.error(f"Database error: {e}")
        return False

st.title("🩺 UB Med Practice Generator - Faculty Portal")

data = load_cloud_data()

# --- COURSE SELECTION & CREATION ---
st.subheader("1. Select or Create Course")
col1, col2 = st.columns([2, 1])

with col1:
    course_list = list(data.keys()) if data else []
    selected_course = st.selectbox("Select Existing Course:", options=["-- Select Course --"] + course_list)

with col2:
    new_course_input = st.text_input("Or Create New Course:")
    if st.button("➕ Create Course"):
        clean_course = new_course_input.strip()
        if clean_course:
            if clean_course not in data:
                # Under-the-hood fix: Ensure 'sessions' dictionary exists so saving new sessions won't crash
                data[clean_course] = {
                    "sessions": {},
                    "global_style_profile": ""
                }
                if save_cloud_data(data):
                    st.success(f"Course '{clean_course}' created! You can now select it on the left.")
                    st.rerun()
            else:
                st.warning("Course already exists.")
        else:
            st.error("Please enter a course name.")

st.markdown("---")

if selected_course and selected_course != "-- Select Course --":
    st.subheader(f"2. Manage Sessions for: {selected_course}")
    
    # Ensure nested dictionary keys exist safely
    course_data = data.get(selected_course, {})
    if not isinstance(course_data, dict):
        course_data = {"sessions": {}, "global_style_profile": ""}
    if "sessions" not in course_data:
        course_data["sessions"] = {}
        
    session_title = st.text_input("Session / Lecture Title:")
    session_date = st.date_input("Lecture Date:")
    sess_style = st.text_area("Session-Specific Faculty Style Guidelines (Optional):")
    slides_text = st.text_area("Full Slide Deck Contents / Text:", height=250)
    
    if st.button("💾 Save Session", type="primary"):
        if not session_title.strip():
            st.error("Please enter a Session Title.")
        elif not slides_text.strip():
            st.error("Please provide the slide deck contents.")
        else:
            data[selected_course] = course_data
            data[selected_course]["sessions"][session_title.strip()] = {
                "date": str(session_date),
                "style_profile": sess_style.strip(),
                "slides": slides_text.strip()
            }
            if save_cloud_data(data):
                st.success(f"Session '{session_title}' saved successfully under '{selected_course}'!")
                st.rerun()
