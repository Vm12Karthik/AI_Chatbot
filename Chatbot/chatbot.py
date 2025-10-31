# chatbot.py

import os
import streamlit as st
import sqlite3
from openai import OpenAI
from groq import Groq
from config import OPENAI_API_KEY, GROQ_API_KEY

# Optional PDF extraction
try:
    import PyPDF2
    _HAS_PYPDF2 = True
except Exception:
    _HAS_PYPDF2 = False

# ---- LLM provider helpers ----------------------------------------------------
def get_provider_client(provider: str):
    """
    Lazily import and build the right client for the selected provider.
    Returns (client, model_name, err_msg_if_any).
    """
    provider = provider.lower()
    if provider == "openai":
        if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"):
            return None, None, "OpenAI key missing/invalid. Set OPENAI_API_KEY (starts with 'sk-')."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            # Pick a sensible/chatty, affordable model
            return client, "gpt-3.5-turbo", None
            # You can switch to "gpt-4o-mini" or others anytime.
        except Exception as e:
            return None, None, f"Failed to init OpenAI client: {e}"

    # default: Groq
    if not GROQ_API_KEY or not GROQ_API_KEY.startswith("gsk_"):
        return None, None, "Groq key missing/invalid. Set GROQ_API_KEY (starts with 'gsk_')."
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        return client, "llama-3.1-8b-instant", None  # or "llama-3.1-70b-versatile"
    except Exception as e:
        return None, None, f"Failed to init Groq client: {e}"

def llm_chat(provider: str, client, model: str, messages, max_tokens=300, temperature=0.7):
    """
    Unified chat call for OpenAI & Groq (both expose client.chat.completions.create).
    Returns answer string or raises Exception.
    """
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    # Both SDKs return choices[0].message.content
    return resp.choices[0].message.content.strip()

# ---- App folders -------------------------------------------------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = "users.db"

# ---- DB helpers --------------------------------------------------------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_users_table():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
        conn.commit()

def insert_user(username, password):
    try:
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def user_exists(username, password):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE username=? AND password=?", (username, password))
        return c.fetchone() is not None

def create_chat_table():
    with get_conn() as conn:
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

def save_chat_to_db(username, user_text, attachment_summary, bot_text):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO chats (username, user_text, attachment_summary, bot_text) VALUES (?, ?, ?, ?)",
                  (username, user_text, attachment_summary, bot_text))
        conn.commit()

def load_chats_for_user(username, limit=200):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""SELECT user_text, attachment_summary, bot_text
                     FROM chats WHERE username=? ORDER BY id ASC LIMIT ?""",
                  (username, limit))
        return c.fetchall()

# ---- Init DB -----------------------------------------------------------------
create_users_table()
create_chat_table()

# ---- Session defaults --------------------------------------------------------
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username"  not in st.session_state: st.session_state.username  = ""
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "provider" not in st.session_state: st.session_state.provider = "Groq"  # default free option

# ---- UI ----------------------------------------------------------------------
st.set_page_config(page_title="AI Assistant Chatbot", page_icon="🤖", layout="centered")

# Sidebar branding
if os.path.exists("image.png"):
    st.sidebar.image("image.png", use_container_width=True)
else:
    st.sidebar.markdown("### 🤖 AI Chatbot")

# Provider switch
st.sidebar.markdown("#### Model Provider")
provider_choice = st.sidebar.radio("Choose provider:", ["Groq", "OpenAI"], index=0 if st.session_state.provider=="Groq" else 1)
st.session_state.provider = provider_choice

# Provider status
client, default_model, init_err = get_provider_client(st.session_state.provider)
if init_err:
    st.sidebar.error(init_err)
else:
    st.sidebar.success(f"{st.session_state.provider} ready ✓ (model: {default_model})")

st.sidebar.markdown("---")
st.sidebar.header("User Panel")

# Auth area
if st.session_state.logged_in:
    st.sidebar.markdown(f"**Logged in as:** `{st.session_state.username}`")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.chat_history = []
        st.rerun()
else:
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

# ---- Main --------------------------------------------------------------------
st.title("🤖 Smart AI Chatbot")
st.write("Ask anything — coding, study help, brainstorming, tasks. You can also upload files (images/PDF/TXT).")

if st.session_state.logged_in:

    # File upload
    uploaded_file = st.file_uploader("Attach file (optional)", type=["png", "jpg", "jpeg", "pdf", "txt", "md"])
    attached_summary = ""
    if uploaded_file:
        path = os.path.join("uploads", uploaded_file.name)
        with open(path, "wb") as f: f.write(uploaded_file.getbuffer())

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

    # Chat box
    user_input = st.text_area("You:", height=120)
    if st.button("Send"):
        if not user_input.strip():
            st.warning("Please type a message.")
        elif init_err:
            st.error(init_err)
        else:
            with st.spinner("Thinking..."):
                content = user_input.strip()
                if attached_summary:
                    content += "\n\n" + attached_summary

                msgs = [
                    {"role": "system",
                     "content": "You are a friendly, general-purpose AI assistant. Be concise, clear, and helpful."},
                    {"role": "user", "content": content}
                ]

                try:
                    # One call that works for both OpenAI & Groq clients
                    answer = llm_chat(st.session_state.provider, client, default_model, msgs,
                                      max_tokens=300, temperature=0.7)
                except Exception as e:
                    # Distinguish quota/invalid key where possible; otherwise generic.
                    e_msg = str(e)
                    if "insufficient_quota" in e_msg or "quota" in e_msg or "401" in e_msg:
                        st.warning("⚠️ Provider rejected the request (invalid key or no credits).")
                    else:
                        st.error(f"⚠️ API error: {e}")
                    answer = "I'm unable to reach the AI service right now. Please check the selected provider & API key."

                # Save & show
                st.session_state.chat_history.append((user_input.strip(), attached_summary, answer))
                save_chat_to_db(st.session_state.username, user_input.strip(), attached_summary, answer)

    # History
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
st.caption("🤖 AI Chatbot © 2025 | OpenAI & Groq compatible")


