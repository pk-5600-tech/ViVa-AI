import streamlit as st
from rag.pdf_loader import extract_text_from_pdf
from rag.text_splitter import split_text
from rag.vector_store import create_vector_store
from rag.retriever import retrieve_chunks
from rag.embeddings import load_embeddings
from llm.response_generator import generate_response
from llm.client import LLMError
from utils.memory import add_turn, clear_history
from utils.session_manager import initialize_session
from modules.presentation_generator import(
    show_presentation_generator
)
from modules.mock_viva import show_mock_viva
#from archive.presentation_practice import show_practice_mode
from modules.final_report import show_final_report
import json
import os
import re
import hashlib
import socket
from utils.paths import PROJECT_ROOT, PAPER_CONTEXT_PATH, PRACTICE_RESULTS_PATH

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ViVaMaTe AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

initialize_session()

for key, default in [
    ("authenticated", False),
    ("active_page", "Dashboard"),
    ("workspace_navigation", "Dashboard"),
    ("show_password", False),
    ("user_email", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

PERSONAS = {
    "professor":        ("📚 Professor",        "Academic, rigorous, structured"),
    "student":          ("🌱 Student",           "Simple, curious, relatable"),
    "skeptic":          ("🔍 Skeptic",           "Critical, probing, questioning"),
    "industry_expert":  ("💼 Industry Expert",   "Practical, deployment-focused"),
    "interviewer":      ("🎯 Interviewer",       "Probing, interview-style"),
}

def navigate_to(page):
    st.session_state.active_page = page
    st.session_state.workspace_navigation = page


def local_service_available(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def clear_paper_dependent_state():
    defaults = {
        "paper_context": None,
        "paper_hash": None,
        "paper_name": None,
        "chunks": [],
        "faiss_index": None,
        "chat_history": [],
        "generated_summary": None,
        "generated_outline": None,
        "generated_questions": None,
        "viva_history": [],
        "viva_question": None,
        "viva_question_persona": None,
        "answer_transcript": "",
        "viva_evaluation": None,
        "viva_results": {},
    }
    for key, value in defaults.items():
        st.session_state[key] = value

# ── Global Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ---------- Base ---------- */
    html, body, [class*="css"], .stApp, .stMarkdown, .stChatMessage {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .stApp {
        background:
            radial-gradient(1200px 700px at 8% -10%, rgba(139,92,246,0.35), transparent 60%),
            radial-gradient(1000px 600px at 100% 10%, rgba(16,185,129,0.22), transparent 60%),
            radial-gradient(900px 500px at 50% 110%, rgba(236,72,153,0.18), transparent 60%),
            linear-gradient(135deg, #0a0b14 0%, #141832 45%, #0d0f1c 100%);
        background-attachment: fixed;
        color: #e6e8ef;
    }
    [data-testid="stHeader"] { background: transparent !important; }

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {
    padding-top: 2rem;
    padding-bottom: 6rem;
    max-width: 1200px;
}

    /* ---------- Typography ---------- */
    h1, h2, h3, h4 { color: #f4f5fb !important; letter-spacing: -0.02em; }
    h1 { font-weight: 800 !important; }
    p, span, label, div { color: #c7cad6; }
    code, pre, kbd { font-family: 'JetBrains Mono', monospace !important; }

    /* ---------- Hero ---------- */
    .hero {
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(16,185,129,0.06));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
    }
    .hero h1 {
        font-size: 2.1rem !important;
        margin: 0 0 6px 0 !important;
        background: linear-gradient(90deg, #ffffff 0%, #a5b4fc 50%, #6ee7b7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero p { color: #9aa0b4; margin: 0; font-size: 0.98rem; }
    .badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 10px; border-radius: 999px;
        background: rgba(99,102,241,0.15);
        border: 1px solid rgba(99,102,241,0.35);
        color: #c7d2fe; font-size: 0.72rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin-bottom: 10px;
    }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #11142a 0%,
        #0b0d18 60%,
        #0a0b14 100%
    ) !important;

    border-right: 1px solid rgba(139,92,246,0.18);
    box-shadow: 4px 0 30px rgba(0,0,0,0.4);
}
    [data-testid="stSidebar"] > div { background: transparent !important; }
    [data-testid="stSidebarCollapsedControl"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        border-radius: 10px !important;
        color: #fff !important;
        box-shadow: 0 6px 18px rgba(99,102,241,0.45);
        visibility: visible !important; opacity: 1 !important;
    }
    [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
    .sidebar-brand {
        display: flex; align-items: center; gap: 10px;
        padding: 6px 0 14px 0; border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 16px;
    }
    .sidebar-brand .logo {
        width: 36px; height: 36px; border-radius: 10px;
        background: linear-gradient(135deg, #6366f1, #10b981);
        display: flex; align-items: center; justify-content: center;
        font-size: 18px; box-shadow: 0 6px 20px rgba(99,102,241,0.35);
    }
    .sidebar-brand .name { font-weight: 700; color: #f4f5fb; font-size: 1rem; }
    .sidebar-brand .sub { color: #7b8095; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; }

    .section-label {
        font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
        color: #7b8095; text-transform: uppercase;
        margin: 14px 0 8px 0;
    }

    /* ---------- Buttons ---------- */
    .stButton > button {
        border-radius: 10px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        background: rgba(255,255,255,0.03) !important;
        color: #d8dbe7 !important;
        font-weight: 500 !important;
        padding: 0.55rem 0.9rem !important;
        transition: all 0.18s ease !important;
        text-align: left !important;
    }
    .stButton > button:hover {
        background: rgba(99,102,241,0.12) !important;
        border-color: rgba(99,102,241,0.4) !important;
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        color: #ffffff !important;
        box-shadow: 0 8px 24px rgba(99,102,241,0.35) !important;
    }

    /* ---------- File uploader ---------- */
    [data-testid="stFileUploader"] {
        background: rgba(255,255,255,0.025);
        border: 1.5px dashed rgba(255,255,255,0.15);
        border-radius: 14px;
        padding: 8px;
        transition: all 0.2s ease;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(99,102,241,0.5);
        background: rgba(99,102,241,0.05);
    }
    [data-testid="stFileUploader"] section { background: transparent !important; border: none !important; }
    [data-testid="stFileUploader"] small { color: #7b8095 !important; }

    /* ---------- Cards / containers ---------- */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255,255,255,0.025) !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 14px !important;
        backdrop-filter: blur(10px);
    }

    /* ---------- Chat ---------- */
    [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 14px 18px !important;
        margin-bottom: 10px;
    }
    [data-testid="stChatInput"] {
        background: rgba(15,17,28,0.85) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 14px !important;
        backdrop-filter: blur(12px);
    }
    [data-testid="stChatInput"] textarea { color: #f4f5fb !important; }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(255,255,255,0.03);
        padding: 5px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent; border-radius: 8px;
        color: #9aa0b4; font-weight: 500;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(79,70,229,0.25)) !important;
        color: #ffffff !important;
    }

    /* ---------- Source cards ---------- */
    .src-card {
        background: linear-gradient(135deg, rgba(99,102,241,0.06), rgba(16,185,129,0.04));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .src-card:hover { border-color: rgba(99,102,241,0.4); transform: translateY(-1px); }
    .src-head {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }
    .src-title { font-weight: 700; color: #f4f5fb; font-size: 0.95rem; }
    .src-meta {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: #9aa0b4;
        background: rgba(255,255,255,0.05);
        padding: 3px 8px; border-radius: 6px;
    }
    .src-body {
        color: #c7cad6; font-size: 0.88rem; line-height: 1.6;
        border-left: 2px solid rgba(99,102,241,0.5);
        padding-left: 12px; margin-top: 6px;
    }

    /* ---------- Alerts ---------- */
    [data-testid="stAlert"] {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.08);
        backdrop-filter: blur(10px);
    }

    /* ---------- Empty state ---------- */
    .empty {
        text-align: center; padding: 60px 20px;
        background: rgba(255,255,255,0.02);
        border: 1px dashed rgba(255,255,255,0.1);
        border-radius: 18px;
    }
    .empty .icon { font-size: 3rem; margin-bottom: 12px; }
    .empty h3 { margin: 0 0 6px 0 !important; }
    .empty p { color: #7b8095; }

    /* ---------- Metric pills ---------- */
    .pill-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 6px 12px; border-radius: 999px;
        font-size: 0.78rem; color: #c7cad6;
    }
    .pill .dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981; }
    [data-testid="stChatInput"] {
    position: sticky;
    bottom: 1rem;
    z-index: 100;
    }

    .feature-card { background: linear-gradient(145deg,rgba(32,39,76,.78),rgba(16,23,47,.94)); border: 1px solid rgba(148,163,255,.18); border-radius: 18px; padding: 1.25rem 1.35rem; min-height: 168px; box-shadow: 0 14px 36px rgba(2,6,23,.18); transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease; }
    .feature-card:hover { transform: translateY(-3px); border-color: rgba(103,232,249,.4); box-shadow: 0 20px 44px rgba(2,6,23,.32), 0 0 30px rgba(103,232,249,.06); }
    .feature-card h3 { margin: .15rem 0 .55rem; font-size: 1.08rem; color: #f4f6ff !important; }
    .feature-card p { color: #aeb9d2; font-size: .9rem; line-height: 1.55; min-height: 48px; margin-bottom: .2rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { background: rgba(124,92,246,.17); border: 1px solid rgba(167,139,250,.28); border-radius: 10px; }
                  
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("chat_history", []),
    ("chunks", []),
    ("faiss_index", None),
    ("paper_name", None),
    ("persona", "professor"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
uploaded = None
if not st.session_state.authenticated:
    st.markdown('<style>[data-testid="stSidebar"]{display:none}</style>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand">
            <div class="logo">🔬</div>
            <div>
                <div class="name">ViVaMaTe AI</div>
                <div class="sub">Paper Intelligence</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.authenticated:
        with st.container(border=True):
            st.caption("WORKSPACE PROFILE")
            st.markdown(f"**{st.session_state.user_email or 'Local demo'}**")
        if st.button("Log out", use_container_width=True, key="logout"):
            for session_key in list(st.session_state.keys()):
                del st.session_state[session_key]
            st.rerun()

        st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)
        pages = ["Dashboard", "Research Chat", "Presentation Generator", "Mock Viva", "Live Voice Viva", "Presentation Practice", "Final Report"]
        selected_page = st.radio("Navigate", pages, label_visibility="collapsed", key="workspace_navigation")
        if selected_page != st.session_state.active_page:
            st.session_state.active_page = selected_page
            st.rerun()

    st.markdown('<div class="section-label">Research Paper</div>', unsafe_allow_html=True)
    if st.session_state.paper_name:
        st.caption(f"Loaded: {st.session_state.paper_name}")
    else:
        st.caption("No paper indexed")
    if st.session_state.active_page != "Dashboard":
        st.button("Upload or change paper", use_container_width=True, on_click=navigate_to, args=("Dashboard",))

    st.markdown('<div class="section-label">Choose AI Persona</div>', unsafe_allow_html=True)
    for key, (label, desc) in PERSONAS.items():
        if st.button(f"{label}", use_container_width=True,
                     type="primary" if st.session_state.persona == key else "secondary",
                     key=f"persona_{key}"):
            st.session_state.persona = key
            st.rerun()

    active_label, active_desc = PERSONAS[st.session_state.persona]
    st.caption(f"Current Persona~ {active_desc}")

    st.markdown('<div class="section-label">⚙️ Session</div>', unsafe_allow_html=True)
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.chat_history = clear_history()
        st.rerun()

    if st.session_state.paper_name:
        with st.container(border=True):
            st.markdown(f"**Loaded Paper**")
            st.caption(st.session_state.paper_name)
            st.markdown(
                f'<div class="pill-row">'
                f'<span class="pill"><span class="dot"></span>Indexed</span>'
                f'<span class="pill">{len(st.session_state.chunks)} chunks</span>'
                f'</div>',
                unsafe_allow_html=True
            )

# The email/password form keeps the existing local session behavior. There is
# no account provider configured, so credentials are not verified.
if not st.session_state.authenticated:
    st.markdown("""
    <style>
      .stApp {
        background:
          radial-gradient(900px 600px at 12% 12%, rgba(124,58,237,.22), transparent 62%),
          radial-gradient(760px 560px at 88% 82%, rgba(34,211,238,.12), transparent 62%),
          linear-gradient(145deg, #080d1b 0%, #10152b 52%, #0a1020 100%);
        background-attachment: fixed;
      }
      .block-container { max-width: 1180px; padding-top: 7vh; }
      .st-key-login_card {
        max-width: 500px; margin: 0 auto; padding: clamp(1.35rem, 4vw, 2.6rem);
        background: linear-gradient(150deg, rgba(20,27,52,.96), rgba(12,19,38,.97));
        border: 1px solid rgba(167,139,250,.22); border-radius: 24px;
        box-shadow: 0 28px 90px rgba(0,0,0,.42), 0 0 55px rgba(124,58,237,.08);
      }
      .st-key-login_card h1, .st-key-login_card h2, .st-key-login_card h3 { color: #f4f6ff !important; }
      .st-key-login_card [data-testid="stTextInput"] input {
        min-height: 48px; background: rgba(7,13,28,.72); color: #f4f6ff;
        border: 1px solid rgba(148,163,184,.22); border-radius: 11px;
        transition: border-color .18s ease, box-shadow .18s ease;
      }
      .st-key-login_card [data-testid="stTextInput"] input:focus {
        border-color: #8b7bff; box-shadow: 0 0 0 3px rgba(139,123,255,.16);
      }
      .st-key-login_card [data-testid="stButton"] button[kind="primary"] {
        min-height: 48px; border: 0 !important; border-radius: 11px !important;
        background: linear-gradient(105deg, #7657f6 0%, #536df5 58%, #388edb 100%) !important;
        color: white !important; font-weight: 700 !important; text-align: center !important;
        box-shadow: 0 10px 28px rgba(83,109,245,.28) !important;
        transition: transform .18s ease, box-shadow .18s ease, filter .18s ease !important;
      }
      .st-key-login_card [data-testid="stButton"] button[kind="primary"]:hover {
        transform: translateY(-1px); filter: brightness(1.08);
        box-shadow: 0 14px 34px rgba(83,109,245,.38) !important;
      }
      .st-key-toggle_password button {
        min-height: 48px !important; padding: 0 !important; text-align: center !important;
        border-radius: 11px !important; background: rgba(7,13,28,.72) !important;
        border: 1px solid rgba(148,163,184,.22) !important;
      }
      .st-key-forgot_password button {
        min-height: 0 !important; padding: .15rem 0 !important; border: 0 !important;
        background: transparent !important; color: #a9b8ff !important;
        text-align: right !important; box-shadow: none !important;
      }
      .st-key-forgot_password button:hover { color: #d9e2ff !important; text-decoration: underline; transform: none !important; }
      @media (max-width: 700px) {
        .block-container { padding: 5vh 1rem 2rem; }
        .st-key-login_card { padding: 1.4rem; }
      }
    </style>
    """, unsafe_allow_html=True)
    spacer_left, center, spacer_right = st.columns([1, 1.12, 1], gap="large")
    with center:
        panel = st.container(border=True, key="login_card")
        with panel:
            brand_left, brand_right = st.columns([1, 4], vertical_alignment="center")
            with brand_left:
                if os.path.exists("static/logo.png"):
                    st.image("static/logo.png", width=58)
            with brand_right:
                st.markdown("### ViVaMaTe AI")
            st.markdown("## Welcome back")

            email = st.text_input("Email", placeholder="name@university.edu", key="login_email")
            password_col, visibility_col = st.columns([8, 1], vertical_alignment="bottom")
            with password_col:
                password = st.text_input("Password", placeholder="Enter your password", type="default" if st.session_state.show_password else "password", key="login_password")
            with visibility_col:
                if st.button("◉" if st.session_state.show_password else "◎", key="toggle_password", help="Hide password" if st.session_state.show_password else "Show password"):
                    st.session_state.show_password = not st.session_state.show_password
                    st.rerun()

            _, forgot_col = st.columns([1, 1], vertical_alignment="center")
            with forgot_col:
                forgot_clicked = st.button("Forgot Password?", key="forgot_password")
            if forgot_clicked:
                st.info("Password reset is unavailable until an authentication provider and password-reset email service are configured.")

            if st.button("Sign In", key="sign_in_button", type="primary", use_container_width=True):
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
                    st.error("Enter a valid email address.")
                elif not password:
                    st.error("Enter your password.")
                else:
                    st.toast("Local session only: account credentials are not verified.", icon="ℹ️")
                    st.session_state.authenticated = True
                    st.session_state.user_email = email.strip()
                    st.session_state.active_page = "Dashboard"
                    st.rerun()
    st.stop()

# ── PDF Processing ─────────────────────────────────────────────────────────────
dashboard_uploaded = st.session_state.get("dashboard_paper_upload")
if dashboard_uploaded is not None:
    uploaded = dashboard_uploaded

upload_signature = None
if uploaded is not None:
    upload_signature = f"{uploaded.name}:{hashlib.sha256(uploaded.getvalue()).hexdigest()}"

if uploaded is not None and upload_signature != st.session_state.get("paper_hash"):
    clear_paper_dependent_state()
    if PAPER_CONTEXT_PATH.exists():
        PAPER_CONTEXT_PATH.unlink()
    with st.spinner("Reading, chunking, and indexing paper..."):
        paper_context_temp = None
        try:
            text = extract_text_from_pdf(uploaded)
            if not text.strip():
                raise ValueError("No readable text was found in this PDF.")

            paper_context_temp = PAPER_CONTEXT_PATH.with_suffix(".tmp")
            paper_context_temp.write_text(
                json.dumps({"paper_name": uploaded.name, "paper_text": text}, ensure_ascii=False),
                encoding="utf-8",
            )

            chunks = split_text(text)
            if not chunks:
                raise ValueError("This paper did not produce searchable text chunks.")
            index = create_vector_store(chunks, load_embeddings(), uploaded.name)
            paper_context_temp.replace(PAPER_CONTEXT_PATH)
            st.session_state.paper_context = {
            "paper_name": uploaded.name,
            "full_text": text,
            "chunks": chunks,
            "faiss_index": index
}
            st.session_state.chunks = chunks
            st.session_state.faiss_index = index
            st.session_state.paper_name = uploaded.name
            st.session_state.chat_history = clear_history()
            st.session_state.paper_hash = upload_signature

            st.success(f"✅ Indexed {len(chunks)} chunks.")

        except Exception as e:
            if paper_context_temp is not None and paper_context_temp.exists():
                paper_context_temp.unlink()
            if PAPER_CONTEXT_PATH.exists():
                PAPER_CONTEXT_PATH.unlink()
            st.error(str(e))
            st.stop()

# ── Main UI ───────────────────────────────────────────────────────────────────

import base64

with open(PROJECT_ROOT / "static" / "logo.png", "rb") as f:
    logo = base64.b64encode(f.read()).decode()

st.markdown(f"""
<div style="
display:flex;
align-items:center;
gap:15px;
">
    <img src="data:image/png;base64,{logo}" width="70">
    <h1 style="
        margin:0;
        font-size:3rem;
    ">
        ViVaMaTe AI
    </h1>

</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 8])

with col2:
    st.caption("Research Paper Intelligence & Presentation Coach")

if st.session_state.active_page == "Dashboard":
    st.markdown("""
    <style>
      .stApp {
        background:
          radial-gradient(960px 620px at 10% 3%, rgba(124,58,237,.22), transparent 65%),
          radial-gradient(780px 560px at 95% 28%, rgba(34,211,238,.13), transparent 65%),
          linear-gradient(145deg, #080d1b 0%, #10162c 54%, #090f20 100%);
        background-attachment: fixed;
      }
      .block-container { max-width: 1320px; padding-top: 1.8rem; }
      .dashboard-welcome {
        padding: clamp(1.4rem, 3vw, 2.3rem); margin: .5rem 0 1.4rem;
        border: 1px solid rgba(139,123,255,.2); border-radius: 22px;
        background: linear-gradient(112deg, rgba(30,35,75,.86), rgba(15,29,54,.84));
        box-shadow: 0 20px 55px rgba(2,6,23,.24); position: relative; overflow: hidden;
      }
      .dashboard-welcome:after { content: ""; position:absolute; width:250px;height:250px;right:-70px;top:-120px;border-radius:50%;background:rgba(34,211,238,.09);filter:blur(4px); }
      .dashboard-eyebrow { color:#8ee8f4; font-size:.72rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase; }
      .dashboard-welcome h2 { color:#f7f8ff !important; font-size:clamp(1.5rem,3vw,2.15rem); margin:.55rem 0 .35rem; }
      .dashboard-welcome p { color:#b6c1d9; margin:0; max-width:680px; }
      .st-key-dashboard_upload_card { background:linear-gradient(130deg,rgba(21,31,62,.88),rgba(13,23,45,.94)); border:1px solid rgba(103,232,249,.2); border-radius:18px; padding:1.1rem 1.3rem; }
      .st-key-dashboard_upload_card [data-testid="stFileUploader"] { border-color:rgba(103,232,249,.28); }
      @media (max-width: 700px) { .block-container { padding:1rem .85rem 3rem; } }
    </style>
    """, unsafe_allow_html=True)

feature_cards = [
    ("Research Chat", "💬", "Ask grounded questions and inspect paper evidence."),
    ("Presentation Generator", "📊", "Create summaries, slide outlines, takeaways, and viva questions."),
    ("Mock Viva", "🎓", "Practice typed answers with an AI examiner."),
    ("Live Voice Viva", "🎙️", "Answer viva questions aloud and receive feedback."),
    ("Presentation Practice", "🎥", "Review camera, speech, and delivery metrics."),
    ("Final Report", "📈", "Review your preparation and practice summary."),
]

if st.session_state.active_page == "Dashboard":
    name = st.session_state.user_email.split("@")[0] if "@" in st.session_state.user_email else "there"
    st.markdown(f'<section class="dashboard-welcome"><div class="dashboard-eyebrow">YOUR RESEARCH WORKSPACE</div><h2>Welcome back, {name}</h2><p>Move from reading to rehearsal with your paper, AI tools, and practice feedback in one place.</p></section>', unsafe_allow_html=True)
    with st.container(border=True, key="dashboard_upload_card"):
        upload_col, upload_status_col = st.columns([1.15, .85], gap="large", vertical_alignment="center")
        with upload_col:
            st.markdown("### Research paper")
            st.caption("Upload a PDF to prepare paper-grounded chat, summaries, and viva practice.")
            st.file_uploader("Choose a research paper (PDF)", type=["pdf"], key="dashboard_paper_upload")
        with upload_status_col:
            if st.session_state.paper_name and st.session_state.faiss_index:
                st.success(f"Ready · {st.session_state.paper_name}")
                st.caption(f"{len(st.session_state.chunks)} sections indexed for this session")
            else:
                st.info("No paper uploaded yet · your workspace and other features are still available")
    st.subheader("Your AI tools")
    for row in range(2):
        cols = st.columns(3, gap="large")
        for col, card in zip(cols, feature_cards[row * 3:(row + 1) * 3]):
            page, icon, description = card
            with col:
                st.markdown(f'<div class="feature-card"><h3>{icon} {page}</h3><p>{description}</p></div>', unsafe_allow_html=True)
                st.button("Open " + page, key="open_" + page, use_container_width=True, on_click=navigate_to, args=(page,))
    st.stop()

paper_required_pages = {"Research Chat", "Presentation Generator", "Mock Viva", "Live Voice Viva"}
if st.session_state.active_page in paper_required_pages and not st.session_state.paper_context:
    st.title(st.session_state.active_page)
    st.warning("Upload and index a research paper to use this feature. Dashboard and navigation remain available.")
    st.stop()
if st.session_state.active_page == "Presentation Generator":
    show_presentation_generator()
    st.stop()
if st.session_state.active_page == "Mock Viva":
    show_mock_viva()
    st.stop()
if st.session_state.active_page == "Live Voice Viva":
    st.markdown("## 🎤 Live AI Voice Viva")
    st.caption("Start the voice viva Flask server on port 5001 to use this feature.")
    if local_service_available(5001):
        st.components.v1.iframe("http://127.0.0.1:5001", height=850, scrolling=True)
    else:
        st.error("Voice viva is unavailable. Start `python voice_viva/vivapp.py` and refresh this page.")
    st.stop()
if st.session_state.active_page == "Presentation Practice":
    st.markdown("## 🎥 Presentation Practice")
    st.caption("Start the presentation practice Flask server on port 5000 to record and review a session.")
    if local_service_available(5000):
        st.link_button("Open Presentation Practice", "http://127.0.0.1:5000")
    else:
        st.error("Presentation Practice is unavailable. Start `python practice_mode/pracapp.py` and refresh this page.")
    if st.button("Refresh practice results"):
        st.rerun()
    if PRACTICE_RESULTS_PATH.exists():
        try:
            with PRACTICE_RESULTS_PATH.open("r", encoding="utf-8") as f:
                practice_data = json.load(f)
            cols = st.columns(4)
            for col, label, key in zip(cols, ["Confidence", "Engagement", "Eye Contact", "Face Detection"], ["confidence_score", "engagement_score", "eye_contact_rate", "face_detection_rate"]):
                with col:
                    metric_value = practice_data.get(key)
                    display_value = f"{metric_value}%" if isinstance(metric_value, (int, float)) else "Unavailable"
                    st.metric(label, display_value)
            st.write("Strengths", practice_data.get("strengths", []))
            st.write("Improvements", practice_data.get("improvements", []))
            st.write("Filler words", practice_data.get("filler_words", {}))
            if practice_data.get("transcript"):
                st.text_area("Practice transcript", practice_data["transcript"], height=180, disabled=True)
        except Exception as e:
            st.error(f"Unable to load practice data: {e}")
    else:
        st.info("No practice results yet. Complete a session to see metrics here.")
    st.stop()
if st.session_state.active_page == "Final Report":
    show_final_report()
    st.stop()

st.header("Research Chat")
st.caption(f"Current AI persona: {PERSONAS[st.session_state.persona][0]} · Paper: {st.session_state.paper_name}")

if st.session_state.active_page == "Research Chat" and not st.session_state.faiss_index:
    st.markdown("""
        <div class="empty">
            <div class="icon">📄</div>
            <h3>Upload a research paper to begin</h3>
            <p>Drop a PDF into the sidebar to extract, embed, and start your research conversation.</p>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Tabs: Chat & Sources ──────────────────────────────────────────────────────
st.markdown('<style>.stTabs [data-baseweb="tab-list"]{display:none}</style>', unsafe_allow_html=True)
chat_tab, presentation_tab, viva_tab, live_viva_tab, practice_tab, report_tab = st.tabs([
    "💬 Research Chat",
    "📊 Presentation Generator",
    "🎓 Mock Viva",
    "🎤 Live Voice Viva",
    "🎤 Practice Mode",
    "📈 Final Report"
])

with chat_tab:

    # Chat input

    question = st.chat_input(
        "Ask anything about the paper..."
    )
    
    # Render previous chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Auto-scroll
    st.markdown("""
        <script>
        function scrollToBottom() {
            const main = window.parent.document.querySelector('.main');

            if (main) {
                main.scrollTo({
                    top: main.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }

        setTimeout(scrollToBottom, 200);
        </script>
    """, unsafe_allow_html=True)

    if question :

        # User message
        with st.chat_message("user"):
            st.markdown(question)

        # Retrieve chunks
        try:
            chunks = retrieve_chunks(st.session_state.faiss_index, question)
        except Exception as exc:
            st.error(f"Paper search failed: {exc}")
            st.stop()
        if not chunks:
            st.warning("No relevant passages were found in the uploaded paper for that question.")
            st.stop()

        # Assistant response
        with st.chat_message("assistant"):

            with st.spinner(
                f"Thinking as {PERSONAS[st.session_state.persona][0]}..."
            ):

                try:
                    answer = generate_response(
                        question=question,
                        chunks=chunks,
                        persona_key=st.session_state.persona,
                        chat_history=st.session_state.chat_history
                    )
                except LLMError as exc:
                    st.error(str(exc))
                    st.stop()

            st.markdown(answer)

            # Retrieved sources
            with st.expander(
                f"📚 Evidence Used For This Answer ({len(chunks)} chunks)"
            ):
                for i, c in enumerate(chunks):
                    source = c.metadata.get(
                        "source",
                        "Unknown PDF"
                    )

                    chunk_id = c.metadata.get(
                        "chunk_id",
                        "?"
                    )

                    with st.container(border=True):

                        st.markdown(
                            f"**📄 Source {i+1}**"
                        )

                        st.caption(
                            f"{source} • Chunk {chunk_id}"
                        )

                        st.write(
                            c.page_content[:400] + "..."
                        )


        # Save history
        st.session_state.chat_history = add_turn(
            st.session_state.chat_history,
            "user",
            question
        )

        st.session_state.chat_history = add_turn(
            st.session_state.chat_history,
            "assistant",
            answer
        )

st.stop()


# with sources_tab:
#     st.markdown("### 📚 Indexed Knowledge Base")
#     st.caption(f"All {len(st.session_state.chunks)} chunks from **{st.session_state.paper_name}**")

#     if not st.session_state.chunks:
#         st.info("No chunks indexed yet.")
#     else:
#         preview_count = min(30, len(st.session_state.chunks))
#         st.caption(f"Showing first {preview_count} chunks")
#         for i, c in enumerate(st.session_state.chunks[:preview_count]):
#             try:
#                 content = c.page_content if hasattr(c, "page_content") else str(c)
#                 source = c.metadata.get("source", st.session_state.paper_name) if hasattr(c, "metadata") else st.session_state.paper_name
#                 chunk_id = c.metadata.get("chunk_id", i) if hasattr(c, "metadata") else i
#             except Exception:
#                 content = str(c); source = st.session_state.paper_name; chunk_id = i
#             preview = content.replace("\n", " ").strip()[:320]
#             st.markdown(f"""
#                 <div class="src-card">
#                     <div class="src-head">
#                         <div class="src-title">🧩 Chunk {i+1}</div>
#                         <div class="src-meta">{source} · id {chunk_id}</div>
#                     </div>
#                     <div class="src-body">{preview}…</div>
#                 </div>
#             """, unsafe_allow_html=True)
    
with presentation_tab:
        show_presentation_generator()
        with st.expander("📄 Paper Information"):
            st.write(
                st.session_state.paper_context["paper_name"]
            )

            st.write(
                f"Chunks Indexed: {len(st.session_state.paper_context['chunks'])}"
            )
        

with viva_tab:
        show_mock_viva()
with live_viva_tab:
    st.markdown("## 🎤 Live AI Voice Viva")
    st.caption("Interact with your AI examiner using your microphone.")

    st.components.v1.iframe(
        "http://127.0.0.1:5001",
        height=850,
        scrolling=True
    )

with practice_tab:

    st.markdown("## 🎤 ViVaMaTe Practice Mode")

    st.link_button(
        "🚀 Open Practice Mode",
        "http://127.0.0.1:5000"
    )

    if st.button("Refresh"):
        st.rerun()

    st.markdown("---")

    if PRACTICE_RESULTS_PATH.exists():

        try:

            with PRACTICE_RESULTS_PATH.open("r", encoding="utf-8") as f:

                practice_data = json.load(f)

            st.subheader("📊 Last Practice Session")

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Confidence",
                    f"{practice_data.get('confidence_score',0)}%"
                )

            with c2:
                st.metric(
                    "Engagement",
                    f"{practice_data.get('engagement_score',0)}%"
                )

            with c3:
                st.metric(
                    "Eye Contact",
                    f"{practice_data.get('eye_contact_rate',0)}%"
                )

            with c4:
                st.metric(
                    "Face Detection",
                    f"{practice_data.get('face_detection_rate',0)}%"
                )

            left,right = st.columns(2)

            with left:

                st.subheader("💪 Strengths")

                strengths = practice_data.get(
                    "strengths",
                    []
                )

                if strengths:

                    for item in strengths:
                        st.success(item)

                else:
                    st.info(
                        "No strengths available yet."
                    )

            with right:

                st.subheader("📌 Improvements")

                improvements = practice_data.get(
                    "improvements",
                    []
                )

                if improvements:

                    for item in improvements:
                        st.warning(item)

                else:
                    st.success(
                        "No improvements required yet."
                    )

            transcript = practice_data.get(
                "transcript",
                ""
            ).strip()

            if len(transcript.split()) >= 15:

                st.subheader("📝 Practice Transcript")

                st.text_area(
                    "",
                    transcript,
                    height=200
                )   

            fillers = practice_data.get(
                "filler_words",
                {}
            )

            used_fillers = {
                k:v
                for k,v in fillers.items()
                if v > 0
            }

            st.subheader("🗣 Filler Words")

            if used_fillers:

                for word,count in used_fillers.items():

                    st.write(
                        f"**{word}** : {count}"
                    )

            else:

                st.success(
                    "No filler words detected."
                )

        except Exception as e:

            st.error(
                f"Unable to load practice data: {e}"
            )

with report_tab:

    show_final_report()
