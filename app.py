import streamlit as st
import google.generativeai as genai
import json
import os
import time
from datetime import datetime

# --- CONFIGURATION ---
DATA_FILE = "user_data.json"
FREE_LIMIT = 5

st.set_page_config(
    page_title="Gemini Pro Analyst",
    page_icon="✨",
    layout="wide"
)

# --- BACKEND FUNCTIONS ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_chat_history(email, doc_name, question, answer):
    data = load_data()
    if email not in data:
        data[email] = {"history": [], "credits_used": 0}
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = {"time": timestamp, "doc": doc_name, "q": question, "a": answer}
    data[email]["history"].append(entry)
    data[email]["credits_used"] += 1
    save_data(data)

def get_user_stats(email):
    data = load_data()
    if email in data:
        return data[email]["credits_used"], data[email]["history"]
    return 0, []

# --- NEW: VISION ENGINE (Replaces PyPDF2) ---
def upload_to_gemini(uploaded_file):
    """Save uploaded file temporarily and send to Gemini Vision"""
    try:
        # 1. Save to a temporary file on the server
        with open("temp_doc.pdf", "wb") as f:
            f.write(uploaded_file.getvalue())
        
        # 2. Upload to Google AI
        vision_file = genai.upload_file("temp_doc.pdf")
        return vision_file
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

def ask_gemini_vision(model, vision_file, question):
    """Send the file object + question to Gemini"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # We pass the FILE directly, not just text!
            response = model.generate_content([question, vision_file])
            return response.text
        except Exception as e:
            if "429" in str(e):
                time.sleep(10)
            else:
                return f"Error: {e}"
    return "System busy. Please try again."

# --- SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "current_chat" not in st.session_state:
    st.session_state.current_chat = []
if "uploaded_file_ref" not in st.session_state:
    st.session_state.uploaded_file_ref = None

# --- PAGE 1: LOGIN ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("✨ Smart Analyst Login")
        st.info("Log in to access your dashboard.")
        email_input = st.text_input("Enter your Email Address")
        if st.button("Continue", type="primary"):
            if email_input:
                st.session_state.logged_in = True
                st.session_state.user_email = email_input
                st.rerun()

# --- PAGE 2: DASHBOARD ---
else:
    credits_used, history = get_user_stats(st.session_state.user_email)
    credits_left = FREE_LIMIT - credits_used
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### 👤 User Profile")
        st.caption(f"Logged in as: {st.session_state.user_email}")
        st.markdown("---")
        st.write(f"**Credits:** {credits_used}/{FREE_LIMIT}")
        st.progress(min(credits_used / FREE_LIMIT, 1.0))
        
        st.markdown("### 📜 Your History")
        if history:
            for item in reversed(history[-5:]): 
                with st.expander(f"🕒 {item['time'].split(' ')[1]} - {item['doc'][:10]}..."):
                    st.write(f"**Q:** {item['q']}")
                    st.info(f"**A:** {item['a'][:150]}...")
        
        st.markdown("<div style='height: 30vh;'></div>", unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🚪 Log Out"):
            st.session_state.logged_in = False
            st.rerun()

    # --- MAIN AREA ---
    st.title("✨ Document Vision Hub")
    st.caption("Supports: PDFs, Scanned Docs, Charts, Receipts")
    
    uploaded_file = st.file_uploader("Upload Document", type="pdf")

    if uploaded_file:
        # --- VISION LOADING LOGIC ---
        # We only upload to Google ONCE per file to save time
        if st.session_state.uploaded_file_ref is None:
            with st.spinner("🧠 Reading document structure (Vision AI)..."):
                # Fetch Key securely
                if "SYSTEM_API_KEY" in st.secrets:
                    genai.configure(api_key=st.secrets["SYSTEM_API_KEY"])
                    
                    # Upload file to Gemini
                    vision_ref = upload_to_gemini(uploaded_file)
                    st.session_state.uploaded_file_ref = vision_ref
                    st.success("Document analyzed! You can now ask questions about charts, images, or text.")
                else:
                    st.error("🚨 Cloud API Key missing! Check your Secrets settings.")

        # --- CHAT INTERFACE ---
        # Display Chat History
        for msg in st.session_state.current_chat:
            icon = "👤" if msg["role"] == "user" else "✨"
            with st.chat_message(msg["role"], avatar=icon):
                st.markdown(msg["content"])

        # Chat Input
        if credits_left > 0:
            if user_question := st.chat_input("Ask about this document..."):
                
                st.session_state.current_chat.append({"role": "user", "content": user_question})
                with st.chat_message("user", avatar="👤"):
                    st.markdown(user_question)

                with st.chat_message("assistant", avatar="✨"):
                    with st.spinner("Looking at document..."):
                        # Use the Vision Engine
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        bot_reply = ask_gemini_vision(model, st.session_state.uploaded_file_ref, user_question)
                        
                        st.markdown(bot_reply)
                        
                        # Save History
                        if "System busy" not in bot_reply:
                            st.session_state.current_chat.append({"role": "assistant", "content": bot_reply})
                            save_chat_history(st.session_state.user_email, uploaded_file.name, user_question, bot_reply)
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.warning("🔒 Credit limit reached.")
            st.button("Upgrade to Pro")