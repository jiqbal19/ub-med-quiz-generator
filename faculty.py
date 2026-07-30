import streamlit as st
import requests
import json

BIN_ID = str(st.secrets.get("JSONBIN_BIN_ID", "")).strip()
JSONBIN_KEY = str(st.secrets.get("JSONBIN_API_KEY", "")).strip()

def load_cloud_data():
    """Loads all course records from JSONBin."""
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json().get("record", {})
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
    return {}

def save_cloud_data(data):
    """Saves updated course records back to JSONBin."""
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
        st.error(f"Failed to update database: {e}")
        return False

# --- Faculty Interface ---
data = load_cloud_data()

st.sidebar.title("Faculty Dashboard")
action = st.sidebar.radio("Navigation", ["Manage Courses", "Upload Session Slides"])

# 1. CREATE NEW COURSE
if action == "Manage Courses":
    st.header("Course Management")
    new_course_name = st.text_input("New Course Name (e.g., Gastroenterology):")
    
    if st.button("➕ Create Course"):
        clean_name = new_course_name.strip()
        if clean_name:
            if clean_name not in data:
                # CRITICAL SCHEMA FIX: Ensure 'sessions' dict and 'global_style_profile' exist
                data[clean_name] = {
                    "sessions": {},
                    "global_style_profile": ""
                }
                if save_cloud_data(data):
                    st.success(f"Course '{clean_name}' created successfully!")
                    st.rerun()
            else:
                st.warning("Course already exists.")

# 2. UPLOAD SESSIONS TO COURSE
elif action == "Upload Session Slides":
    st.header("Upload Lecture Session")
    
    if not data:
        st.info("No courses available. Please create a course first.")
        st.stop()
        
    selected_course = st.selectbox("Select Target Course:", options=list(data.keys()))
    
    session_title = st.text_input("Session Title (e.g., Gastric Secretion):")
    session_date = st.date_input("Lecture Date:")
    style_profile = st.text_area("Faculty Writing Style Guidelines (Optional):")
    slides_text = st.text_area("Slide Deck Text / Contents:")
    
    if st.button("💾 Save Session"):
        if not session_title.strip() or not slides_text.strip():
            st.error("Please fill in both the Session Title and Slide Deck Contents.")
        else:
            # Ensure course object exists and contains 'sessions' sub-dict
            if selected_course not in data or not isinstance(data[selected_course], dict):
                data[selected_course] = {"sessions": {}, "global_style_profile": ""}
            
            if "sessions" not in data[selected_course]:
                data[selected_course]["sessions"] = {}
                
            # Store session details under the course
            data[selected_course]["sessions"][session_title.strip()] = {
                "date": str(session_date),
                "style_profile": style_profile.strip(),
                "slides": slides_text.strip()
            }
            
            if save_cloud_data(data):
                st.success(f"Session '{session_title}' saved to '{selected_course}'!")
                st.rerun()
