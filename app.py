"""
InvestorOS — Pitch Trainer (Voice + Text + Deck Upload)
Run: streamlit run app.py
"""
import streamlit as st
from google import genai
from google.genai import types
import edge_tts
import asyncio
import nest_asyncio
import pdfplumber
import io
import hashlib
import json
import os, sys

nest_asyncio.apply()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from scripts.csv_client import get_all_funds
from scripts.pitch_trainer import build_persona_prompt, ARCHETYPES

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_profiled_funds():
    """Returns fund names that have a rich research profile JSON."""
    profiles_dir = "data/fund_profiles"
    if not os.path.exists(profiles_dir):
        return []
    names = []
    for fname in sorted(os.listdir(profiles_dir)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(profiles_dir, fname)) as f:
                    data = json.load(f)
                    name = data.get("fund_name", "")
                    if name:
                        names.append(name)
            except Exception:
                continue
    return names


# ── TTS & STT ─────────────────────────────────────────────────────────────────

VOICE_OPTIONS = {
    "Neerja — Indian English, Expressive (recommended)": ("en-IN-NeerjaExpressiveNeural", "+10%"),
    "Prabhat — Indian English, Male":                    ("en-IN-PrabhatNeural",           "+10%"),
    "Andrew — US English, Natural Male":                 ("en-US-AndrewMultilingualNeural", "+10%"),
    "Brian — US English, Friendly Male":                 ("en-US-BrianNeural",              "+10%"),
}

def speak(text, voice_key="Neerja — Indian English, Expressive (recommended)"):
    voice, rate = VOICE_OPTIONS.get(voice_key, ("en-IN-NeerjaExpressiveNeural", "-5%"))
    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
    try:
        return asyncio.run(_run())
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())


def transcribe(client, audio_bytes):
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[
                types.Part(inline_data=types.Blob(mime_type="audio/wav", data=audio_bytes)),
                "Transcribe this audio exactly as spoken. Return only the spoken words, nothing else."
            ]
        )
        return response.text.strip()
    except Exception:
        return None


def chat_respond(chat, user_text):
    try:
        response = chat.send_message(user_text)
        return response.text.strip()
    except Exception:
        return "I didn't catch that. Could you repeat?"


def audio_hash(audio_bytes):
    return hashlib.md5(audio_bytes).hexdigest()


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_deck_text(uploaded_file, max_chars=6000):
    """Extract text from uploaded pitch deck PDF."""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
            full_text = "\n\n".join(pages)
            return full_text[:max_chars]
    except Exception as e:
        return None


def build_deck_context(deck_text):
    """Wraps deck text into a context block for the investor prompt."""
    return f"""
FOUNDER'S PITCH DECK (you have glanced through this before the meeting):
---
{deck_text}
---
This gives you a broad sense of what they're building. Do NOT quiz them on slides or reference it directly.
Let the founder present naturally. If something catches your attention mid-presentation, you may
interrupt briefly with a clarifying question — but only if it genuinely interests you.
Save deeper questions for after they finish walking you through the business.
"""


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Pitch Trainer — InvestorOS",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #1a1f2e;
}
[data-testid="stSidebar"] * {
    color: #e8eaf0 !important;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stFileUploader label {
    color: #ffffff !important;
    font-weight: 500;
}
[data-testid="stSidebar"] .stButton button {
    color: #ffffff !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] .stCaption {
    color: #c0c4d0 !important;
}
[data-testid="stSidebar"] hr {
    border-color: #3a4060 !important;
}
[data-testid="stSidebar"] h2 {
    color: #ffffff !important;
}
.transcript-box {
    background: #1e2530;
    border-left: 3px solid #4a9eff;
    padding: 0.6rem 1rem;
    border-radius: 4px;
    font-style: italic;
    color: #ccc;
    margin: 0.5rem 0;
    font-size: 0.9rem;
}
.deck-badge {
    background: #1a2e1a;
    border-left: 3px solid #4caf50;
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    color: #81c784;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "messages": [],
        "chat": None,
        "started": False,
        "persona_label": "",
        "last_audio_hash": "",
        "deck_text": None,
        "deck_name": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

FEEDBACK_PROMPT = """Step out of the investor role for a moment.
Give the founder honest, structured feedback on their pitch so far:
1. What landed well
2. What was weak or unclear
3. The 2-3 specific things they must fix before the real meeting
Be direct and specific. No fluff."""


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎯 InvestorOS")
    st.caption("Pitch Practice Simulator")
    st.divider()

    # Pitch deck upload
    st.markdown("**Upload Pitch Deck** *(optional)*")
    uploaded_deck = st.file_uploader("PDF only", type=["pdf"], label_visibility="collapsed")
    if uploaded_deck:
        if uploaded_deck.name != st.session_state.deck_name:
            deck_text = extract_deck_text(uploaded_deck)
            if deck_text:
                st.session_state.deck_text = deck_text
                st.session_state.deck_name = uploaded_deck.name
                st.success(f"Deck loaded: {uploaded_deck.name}")
            else:
                st.error("Could not read PDF. Try another file.")
    elif st.session_state.deck_name:
        st.caption(f"Deck: {st.session_state.deck_name}")

    st.divider()

    input_mode = st.radio("Input mode", ["Voice", "Text"])

    if input_mode == "Voice":
        voice_key = st.selectbox("Investor voice", list(VOICE_OPTIONS.keys()))
        st.session_state.voice_key = voice_key
    else:
        st.session_state.voice_key = list(VOICE_OPTIONS.keys())[0]

    st.divider()

    mode = st.radio("Simulate", ["Investor Archetype", "Specific Fund"])

    if mode == "Investor Archetype":
        archetype_labels = {
            "Pequoia": "Large fund — Peak XV / Sequoia / Accel",
            "Zelevation": "Mid-tier — Blume / 3one4 / Elevation",
            "Microfund": "Micro VC — First Cheque / SucSEED",
        }
        archetype = st.selectbox(
            "Fund type",
            list(archetype_labels.keys()),
            format_func=lambda x: f"{x}  ({archetype_labels[x]})"
        )
        selected_fund = None
    else:
        # Only show funds with a rich research profile
        profiled_funds = get_profiled_funds()
        selected_fund = st.selectbox("Select fund", profiled_funds)
        if not profiled_funds:
            st.caption("No fund profiles built yet. Run: python3 run.py research-all")
        archetype = None

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("▶ Start", type="primary", use_container_width=True)
    with col2:
        reset_btn = st.button("↺ Reset", use_container_width=True)

    if reset_btn:
        for k in ["messages", "chat", "started", "persona_label", "last_audio_hash", "deck_text", "deck_name"]:
            st.session_state[k] = [] if k == "messages" else None if k in ["chat", "deck_text", "deck_name"] else False if k == "started" else ""
        st.rerun()

    if st.session_state.started:
        st.divider()
        if input_mode == "Voice":
            st.caption("🎤 Record → stop → wait for investor")
            st.caption("Say **'give me feedback'** for debrief")
        else:
            st.caption("Type **feedback** for debrief")
            st.caption("Type **quit** to end")


# ── Start session ─────────────────────────────────────────────────────────────

if start_btn:
    with st.spinner("Setting up your investor..."):
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        chat = client.chats.create(model="gemini-flash-latest")

        # Build base persona prompt
        if mode == "Investor Archetype":
            persona_prompt = build_persona_prompt(archetype_key=archetype)
            label = archetype
        else:
            funds_data = get_all_funds()
            fund_data = next(
                (f for f in funds_data if f.get("Fund Name", "").strip() == selected_fund),
                None
            )
            persona_prompt = build_persona_prompt(fund_data=fund_data)
            label = selected_fund

        # Append deck context if uploaded
        if st.session_state.deck_text:
            persona_prompt += build_deck_context(st.session_state.deck_text)

        response_text = chat_respond(chat, persona_prompt)
        vk = st.session_state.get("voice_key", list(VOICE_OPTIONS.keys())[0])
        opening_audio = speak(response_text, vk) if input_mode == "Voice" else None

        st.session_state.chat = chat
        st.session_state.gemini_client = client
        st.session_state.messages = [{
            "role": "investor",
            "content": response_text,
            "audio": opening_audio
        }]
        st.session_state.started = True
        st.session_state.persona_label = label
        st.session_state.last_audio_hash = ""
    st.rerun()


# ── Main area ─────────────────────────────────────────────────────────────────

if not st.session_state.started:
    st.title("Pitch Practice")
    st.markdown("Practice your investor pitch with a realistic AI-powered investor. Voice or text — your choice.")

    if st.session_state.deck_name:
        st.markdown(f'<div class="deck-badge">✅ Deck loaded: {st.session_state.deck_name} — investor will have context before the meeting starts</div>', unsafe_allow_html=True)

    st.info("Upload your deck (optional), pick an investor, and click **▶ Start**.")

    with st.expander("How it works"):
        st.markdown("""
        **Pitch deck upload** *(recommended)*
        - Upload your PDF before starting
        - The investor reads it before the meeting — simulating how real meetings work
        - Expect pointed questions about your specific numbers, market claims, and business model

        **Voice mode**
        - Hit record, speak your pitch naturally
        - The investor responds in Indian English voice
        - Say *"give me feedback"* for a structured pitch debrief

        **Text mode**
        - Type your pitch, press Enter
        - Type *feedback* for debrief, *quit* to end

        **Investor types:**
        - **Pequoia** — Large fund. Metrics-heavy, formal, very high bar.
        - **Zelevation** — Mid-tier fund. GTM & distribution focused, founder-friendly.
        - **Microfund** — Micro VC. Bets on people, conversational, first cheque.
        - **Specific Fund** — Pulls real thesis, portfolio, and priorities for 6 prominent India funds (Blume, 3one4, Elevation, India Quotient, Better Capital, 100X.VC).
        """)

else:
    # Show deck badge if deck was uploaded for this session
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.title(f"Pitching: {st.session_state.persona_label}")
    with header_col2:
        if st.session_state.deck_name:
            st.markdown(f'<div class="deck-badge" style="margin-top:1rem">📄 Deck loaded</div>', unsafe_allow_html=True)

    st.divider()

    # Chat history
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "investor":
            with st.chat_message("assistant", avatar="💼"):
                st.write(msg["content"])
                if msg.get("audio") and i == len(st.session_state.messages) - 1:
                    st.audio(msg["audio"], format="audio/mp3", autoplay=True)
                elif msg.get("audio"):
                    st.audio(msg["audio"], format="audio/mp3", autoplay=False)
        else:
            with st.chat_message("user", avatar="🧑‍💼"):
                if msg.get("transcript"):
                    st.markdown(f'<div class="transcript-box">🎤 {msg["transcript"]}</div>', unsafe_allow_html=True)
                else:
                    st.write(msg["content"])

    st.divider()

    # ── Voice input ───────────────────────────────────────────────────────────
    if input_mode == "Voice":
        audio_input = st.audio_input("🎤 Record your response")

        if audio_input is not None:
            raw_bytes = audio_input.read()
            current_hash = audio_hash(raw_bytes)

            if current_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = current_hash

                with st.spinner("Transcribing..."):
                    client = st.session_state.get("gemini_client") or genai.Client(api_key=config.GEMINI_API_KEY)
                    transcript = transcribe(client, raw_bytes)

                if not transcript:
                    st.warning("Could not transcribe. Please try again.")
                else:
                    lower = transcript.lower()
                    if any(kw in lower for kw in ["give me feedback", "feedback please", "debrief"]):
                        user_text = FEEDBACK_PROMPT
                        display_transcript = "give me feedback"
                    elif any(kw in lower for kw in ["quit", "end session", "stop session"]):
                        st.session_state.messages.append({"role": "founder", "content": "quit", "transcript": "end session"})
                        st.session_state.messages.append({
                            "role": "investor",
                            "content": "Okay, we'll wrap up here. All the best for your fundraise.",
                            "audio": speak("Okay, we'll wrap up here. All the best for your fundraise.", st.session_state.get("voice_key", list(VOICE_OPTIONS.keys())[0]))
                        })
                        st.session_state.started = False
                        st.rerun()
                        st.stop()
                    else:
                        user_text = transcript
                        display_transcript = transcript

                    st.session_state.messages.append({
                        "role": "founder",
                        "content": user_text,
                        "transcript": display_transcript
                    })

                    with st.spinner("Investor thinking..."):
                        response_text = chat_respond(st.session_state.chat, user_text)

                    with st.spinner("Generating voice response..."):
                        response_audio = speak(response_text, st.session_state.get("voice_key", list(VOICE_OPTIONS.keys())[0]))

                    st.session_state.messages.append({
                        "role": "investor",
                        "content": response_text,
                        "audio": response_audio
                    })
                    st.rerun()

    # ── Text input ────────────────────────────────────────────────────────────
    else:
        user_input = st.chat_input("Your response...")

        if user_input:
            lower = user_input.strip().lower()

            if lower == "quit":
                st.session_state.messages.append({"role": "founder", "content": "quit"})
                st.session_state.messages.append({
                    "role": "investor",
                    "content": "Okay, we'll wrap up here. All the best for your fundraise.",
                    "audio": None
                })
                st.session_state.started = False
                st.rerun()
                st.stop()
            elif lower == "feedback":
                user_text = FEEDBACK_PROMPT
            else:
                user_text = user_input

            st.session_state.messages.append({"role": "founder", "content": user_input})

            with st.spinner("Investor thinking..."):
                response_text = chat_respond(st.session_state.chat, user_text)

            st.session_state.messages.append({
                "role": "investor",
                "content": response_text,
                "audio": None
            })
            st.rerun()
