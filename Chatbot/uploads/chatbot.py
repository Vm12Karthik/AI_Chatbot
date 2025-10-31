# chatbot.py

import os
import streamlit as st
import sqlite3
from openai import OpenAI
from config import OPENAI_API_KEY

# Optional PDF extraction
try:
    import PyPDF2
    _HAS_PYPDF2 = True
except Exception:
    _HAS_PYPDF2 = False

client = OpenAI(api_key=OPENAI_API_KEY)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------- DATABASE ----------------
DB_PATH = "users.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_users_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    conn.commit()
    conn.close()

def insert_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def user_exists(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    res = c.fetchone()
    conn.close()
    return res is not None

# --- Chat history DB helpers ---
def create_chat_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            user_text TEXT,
            attachment_summary TEXT,
            bot_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_chat_to_db(username, user_text, attachment_summary, bot_text):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO chats (username, user_text, attachment_summary, bot_text) VALUES (?, ?, ?, ?)",
              (username, user_text, attachment_summary, bot_text))
    conn.commit()
    conn.close()

def load_chats_for_user(username, limit=200):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_text, attachment_summary, bot_text FROM chats WHERE username=? ORDER BY id ASC LIMIT ?",
              (username, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# init tables
create_users_table()
create_chat_table()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------- UI ----------------
st.set_page_config(page_title="AI Assistant Chatbot", page_icon="🤖", layout="centered")

# Sidebar
if os.path.exists("image.png"):
    st.sidebar.image("image.png", use_container_width=True)
else:
    st.sidebar.markdown("### 🤖 AI Chatbot")

st.sidebar.header("User Panel")

# If logged in: show username & logout
if st.session_state.logged_in:
    st.sidebar.markdown(f"**Logged in as:** `{st.session_state.username}`")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.chat_history = []
        st.rerun()

else:
    # Register
    st.sidebar.subheader("Register")
    reg_user = st.sidebar.text_input("Username", key="reg_user")
    reg_pass = st.sidebar.text_input("Password", type="password", key="reg_pass")
    if st.sidebar.button("Register"):
        if not reg_user or not reg_pass:
            st.sidebar.warning("Enter both username and password.")
        elif insert_user(reg_user.strip(), reg_pass):
            st.session_state.logged_in = True
            st.session_state.username = reg_user.strip()
            st.session_state.chat_history = load_chats_for_user(st.session_state.username)
            st.sidebar.success("✅ Registered & logged in!")
            st.rerun()
        else:
            st.sidebar.error("❌ Username exists. Try login.")

    st.sidebar.markdown("---")
    # Login
    st.sidebar.subheader("Login")
    log_user = st.sidebar.text_input("Username", key="login_user")
    log_pass = st.sidebar.text_input("Password", type="password", key="login_pass")
    if st.sidebar.button("Login"):
        if user_exists(log_user.strip(), log_pass):
            st.session_state.logged_in = True
            st.session_state.username = log_user.strip()
            st.session_state.chat_history = load_chats_for_user(st.session_state.username)
            st.sidebar.success(f"Welcome, {st.session_state.username}! 👋")
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid credentials.")

# ---------------- MAIN ----------------
st.title("🤖 Smart AI Chatbot")
st.write("Ask anything — general questions, coding doubts, productivity help, ideas, knowledge… \n\nYou can also upload files!")

if st.session_state.logged_in:
    uploaded_file = st.file_uploader("Attach file (optional)", type=["png", "jpg", "jpeg", "pdf", "txt", "md"])
    attached_summary = ""
    if uploaded_file:
        path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        if uploaded_file.type.startswith("image/"):
            st.image(path, caption=uploaded_file.name, use_container_width=True)
            attached_summary = f"[Image attached: {uploaded_file.name}]"
        elif uploaded_file.name.lower().endswith((".txt", ".md")):
            try:
                txt = uploaded_file.getvalue().decode("utf-8", errors="ignore")[:4000]
                st.text_area("Extracted text (truncated):", value=txt, height=200)
                attached_summary = f"[Document: {uploaded_file.name}]\n{txt}"
            except:
                attached_summary = f"[File attached: {uploaded_file.name}]"
        elif uploaded_file.name.lower().endswith(".pdf"):
            if _HAS_PYPDF2:
                try:
                    with open(path, "rb") as f:
                        pdf = PyPDF2.PdfReader(f)
                        text = "".join(p.extract_text() or "" for p in pdf.pages)[:4000]
                        st.text_area("Extracted PDF (truncated):", value=text, height=200)
                        attached_summary = f"[PDF: {uploaded_file.name}]\n{text}"
                except:
                    attached_summary = f"[PDF attached: {uploaded_file.name} — unreadable]"
            else:
                attached_summary = f"[PDF attached: {uploaded_file.name}]"

    user_input = st.text_area("You:", height=120)
    if st.button("Send"):
        if not user_input.strip():
            st.warning("Please type a message.")
        else:
            with st.spinner("Thinking..."):
                content = user_input.strip()
                if attached_summary:
                    content += "\n\n" + attached_summary
                msgs = [
                    {"role": "system", "content": "You are a friendly, general-purpose AI assistant. Help with any topic politely and clearly."},
                    {"role": "user", "content": content}
                ]
                try:
                    resp = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=msgs,
                        max_tokens=300,
                        temperature=0.7
                    )
                    answer = resp.choices[0].message.content.strip()
                except Exception as e:
                    if "insufficient_quota" in str(e) or "429" in str(e):
                        st.warning("⚠️ No OpenAI credits — using offline response.")
                        answer = ("I am currently offline. Try again later or add API credits. "
                                  "Meanwhile, general tip: stay curious and keep learning! 🚀")
                    else:
                        st.error(f"⚠️ API error: {e}")
                        answer = "Error reaching AI service."
                
                st.session_state.chat_history.append((user_input.strip(), attached_summary, answer))
                save_chat_to_db(st.session_state.username, user_input.strip(), attached_summary, answer)

    # Display history
    if st.session_state.chat_history:
        st.markdown("### 💬 Chat History")
        for u, a, b in st.session_state.chat_history:
            st.markdown(f"**You:** {u}")
            if a:
                st.markdown(f"_Attachment:_ {a}")
            st.markdown(f"**AI:** {b}")
            st.write("---")

else:
    st.info("Please login or register to start chatting.")

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("🤖 AI Chatbot © 2025 | Built with Streamlit & OpenAI GPT-3.5")

