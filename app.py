import streamlit as st
import google.generativeai as genai
import PyPDF2 as pdf
import json
import os
import time
from datetime import datetime

# --- CONFIGURATION ---
DATA_FILE = "user_data.json"
FREE_LIMIT = 5
# ⬇️ PASTE YOUR KEY HERE
# Securely fetch key from cloud secrets
SYSTEM_API_KEY = st.secrets["SYSTEM_API_KEY"]

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

def extract_text(uploaded_file):
    try:
        reader = pdf.PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except:
        return None

# --- IMPROVED RETRY LOGIC ---
def ask_gemini_with_retry(model, prompt):
    # Try 3 times, waiting longer each time (10s, 20s, 30s)
    wait_times = [10, 20, 30] 
    
    for i, wait_seconds in enumerate(wait_times):
        try:
            return model.generate_content(prompt).text
        except Exception as e:
            if "429" in str(e):
                # Show a progress bar so user knows we are waiting
                progress_text = f"🚦 High traffic (Free Tier). Retrying in {wait_seconds} seconds..."
                my_bar = st.progress(0, text=progress_text)
                
                for percent_complete in range(100):
                    time.sleep(wait_seconds / 100)
                    my_bar.progress(percent_complete + 1, text=progress_text)
                
                my_bar.empty() # Remove bar after waiting
            else:
                return f"⚠️ Technical Error: {str(e)}"
    
    return "❌ System is extremely busy. Please wait 2 minutes before asking again."

# --- SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "current_chat" not in st.session_state:
    st.session_state.current_chat = []

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
        if not history:
            st.caption("No history yet.")
        else:
            for item in reversed(history[-5:]): 
                with st.expander(f"🕒 {item['time'].split(' ')[1]} - {item['doc'][:10]}..."):
                    st.write(f"**Q:** {item['q']}")
                    st.info(f"**A:** {item['a'][:150]}...")
        
        st.markdown("<div style='height: 50vh;'></div>", unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🚪 Log Out"):
            st.session_state.logged_in = False
            st.rerun()

    # --- MAIN AREA ---
    st.title("✨ Document Intelligence Hub")
    uploaded_file = st.file_uploader("Upload PDF Document", type="pdf")

    if uploaded_file:
        text_content = extract_text(uploaded_file)
        
        if text_content:
            # Display Chat History
            for msg in st.session_state.current_chat:
                icon = "👤" if msg["role"] == "user" else "✨"
                with st.chat_message(msg["role"], avatar=icon):
                    st.markdown(msg["content"])

            # Input Area
            if credits_left > 0:
                if user_question := st.chat_input("Ask a question about this document..."):
                    
                    # User Message
                    st.session_state.current_chat.append({"role": "user", "content": user_question})
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(user_question)

                    # AI Response
                    if SYSTEM_API_KEY == "PASTE_YOUR_KEY_HERE":
                        st.error("🚨 Developer Error: API Key is missing in code (Line 16).")
                    else:
                        with st.chat_message("assistant", avatar="✨"):
                            with st.spinner("Analyzing..."):
                                try:
                                    genai.configure(api_key=SYSTEM_API_KEY)
                                    model = genai.GenerativeModel('gemini-flash-latest')
                                    prompt = f"Document: {text_content}\nQuestion: {user_question}\nAnswer:"
                                    
                                    # Call the Improved Retry Function
                                    bot_reply = ask_gemini_with_retry(model, prompt)
                                    
                                    st.markdown(bot_reply)
                                    
                                    # Save only if successful
                                    if "Technical Error" not in bot_reply and "System is extremely busy" not in bot_reply:
                                        st.session_state.current_chat.append({"role": "assistant", "content": bot_reply})
                                        save_chat_history(st.session_state.user_email, uploaded_file.name, user_question, bot_reply)
                                        time.sleep(0.5)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")

            else:
                st.warning("🔒 Free limit reached.")
                st.info("Check the sidebar to see your past answers.")
                st.button("Upgrade to Pro")