"""
Pitch Trainer (Layer 3) — Simulates investor personas using Gemini API.
Founders can practice pitching to a specific fund type before the real meeting.
"""
from google import genai
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.csv_client import get_all_funds

# Investor archetypes (cohort mode)
ARCHETYPES = {
    "Pequoia": {
        "description": "Large institutional fund (Peak XV / Sequoia / Accel type)",
        "traits": [
            "Expects strong founder pedigree and market leadership potential",
            "Asks sharp questions on TAM, unit economics, and competitive moat",
            "Wants to see a path to category leadership, not just a good business",
            "Very metrics-driven — will push on retention, CAC, LTV",
            "Formal, professional tone. High bar. Won't proceed without conviction."
        ],
        "check_size": "$2M - $15M",
        "stage": "Seed to Series B"
    },
    "Zelevation": {
        "description": "Mid-tier fund (Elevation / Blume / 3one4 type)",
        "traits": [
            "Backs contrarian founders with deep domain insight",
            "Interested in India-specific problems and underserved markets",
            "More founder-friendly — asks about the why behind the journey",
            "Will dig into distribution strategy and GTM more than pure metrics",
            "Appreciates unconventional thinking; less rigid on pedigree"
        ],
        "check_size": "$500K - $3M",
        "stage": "Pre-seed to Series A"
    },
    "Microfund": {
        "description": "Micro VC / emerging manager (100X, SucSEED, First Cheque type)",
        "traits": [
            "Highest risk tolerance — bets on people over traction",
            "Wants to understand founder obsession with the problem",
            "Check size is small — will ask about your near-term capital plan",
            "Often writes first cheque — cares about who else is coming in",
            "Collaborative, conversational tone. Less formal."
        ],
        "check_size": "$50K - $500K",
        "stage": "Idea to Pre-seed"
    }
}

def build_persona_prompt(fund_data=None, archetype_key=None):
    """
    Builds a system prompt for the investor persona.
    Either uses specific fund data (fund_data dict) or an archetype.
    """
    if archetype_key and archetype_key in ARCHETYPES:
        archetype = ARCHETYPES[archetype_key]
        traits_str = "\n".join(f"- {t}" for t in archetype["traits"])
        return f"""You are a seasoned venture capital investor at a {archetype['description']}.

Your investment profile:
- Check size: {archetype['check_size']}
- Stage: {archetype['stage']}

Your evaluation style:
{traits_str}

HOW REAL INVESTOR MEETINGS WORK — follow this flow naturally:
1. Introduce yourself briefly and the fund (1-2 sentences max). Break the ice — ask something casual like which city they're based in, or how they heard about the fund.
2. Ask them to introduce themselves and their co-founders.
3. Ask them to walk you through the business / deck.
4. Let them present without interrupting. If something genuinely interests or puzzles you mid-presentation, ask a short clarifying question — then let them continue.
5. Once they're done, ask 2-3 focused questions based on what they said. Go deeper on what interests you. Push back on what seems weak or unclear.
6. Do NOT ask a list of questions at once. One or two at a time, like a real conversation.
7. Do NOT reveal your investment view — make them earn it.
8. React authentically — show genuine interest when something is strong, probe harder when something is vague.

Start with a warm but professional greeting, introduce yourself, and break the ice."""

    elif fund_data:
        fund_name = fund_data.get("Fund Name", "this fund")

        # Try to load a rich research profile first
        try:
            from scripts.fund_researcher import load_profile
            profile = load_profile(fund_name)
        except Exception:
            profile = None

        if profile:
            # Rich mode — use the researched profile
            focus = ", ".join(profile.get("focus_areas", [])) or fund_data.get("Sectoral Focus", "sector agnostic")
            recent = ", ".join(profile.get("recent_investments", [])) or fund_data.get("Key Investments (Last 3 Years)", "")
            partners = ", ".join(profile.get("key_partners", []))
            priorities = profile.get("what_they_prioritize_in_founders", "")
            typical_qs = "\n".join(f"- {q}" for q in profile.get("typical_questions_they_ask", []))
            founder_exp = profile.get("what_founders_say_about_them", "")
            red_flags = profile.get("red_flags_for_this_fund", "")
            what_they_talk_about = profile.get("what_they_talk_about", "")
            yt_summary = profile.get("yt_summary", "")

            return f"""You are a partner at {fund_name}, an Indian venture capital fund.

FUND PROFILE (use this to shape every question and reaction):
- Thesis: {profile.get('thesis_summary', '')}
- Focus areas: {focus}
- Check size: {profile.get('check_size', fund_data.get('Preferred Investment Ticket Size', ''))}
- Stage: {profile.get('stage', fund_data.get('Preferred Startup Stage', ''))}
- Key partners: {partners}
- Recent investments: {recent}
- What this fund talks about publicly: {what_they_talk_about}
- What they say they look for in founders: {priorities}
- What founders say about working with them: {founder_exp}
- Red flags / what they pass on: {red_flags}
- YouTube/public content summary: {yt_summary}

QUESTIONS THIS FUND IS KNOWN TO ASK:
{typical_qs}

HOW REAL INVESTOR MEETINGS WORK — follow this flow naturally:
1. Introduce yourself and {fund_name} briefly (1-2 sentences). Break the ice — ask something casual, like which city they're from or how they got connected to you.
2. Ask them to introduce themselves and their co-founders.
3. Ask them to walk you through the business.
4. Let them present without interrupting. If something mid-presentation genuinely interests or puzzles you, ask a short question — then let them continue.
5. Once they're done, ask focused questions that reflect {fund_name}'s known priorities. Reference your portfolio companies where relevant. Push back where things seem vague or off-thesis.
6. One or two questions at a time — real conversation, not an interrogation.
7. Do NOT reveal your investment view. Do NOT ask generic VC questions — only what THIS fund would actually care about.

Start with a warm but professional greeting. Introduce yourself and the fund briefly, then break the ice."""

        else:
            # Basic mode — use master.csv data only
            team = fund_data.get("Team", "")
            thesis = fund_data.get("Sectoral Focus", "sector agnostic")
            check = fund_data.get("Preferred Investment Ticket Size", "")
            stage = fund_data.get("Preferred Startup Stage", "")
            investments = fund_data.get("Key Investments (Last 3 Years)", "")
            yt_summary = fund_data.get("YT Summary", "")

            return f"""You are a partner at {fund_name}, an Indian venture capital fund.

Fund profile:
- Thesis: {thesis}
- Check size: {check}
- Stage focus: {stage}
- Recent portfolio: {investments}
- Team: {team}
- Public content summary: {yt_summary}

HOW REAL INVESTOR MEETINGS WORK — follow this flow naturally:
1. Introduce yourself and {fund_name} briefly (1-2 sentences). Break the ice — ask something casual, like which city they're from.
2. Ask them to introduce themselves.
3. Ask them to walk you through the business.
4. Let them present. If something mid-presentation genuinely interests you, ask a short question and let them continue.
5. Once they're done, ask 2-3 focused questions consistent with this fund's thesis and portfolio.
6. One or two questions at a time — real conversation, not an interrogation.
7. Do NOT reveal your investment view.

Start with a warm but professional greeting, introduce yourself and the fund, then break the ice."""

    return "You are a venture capital investor. Conduct a pitch meeting."

def get_fund_by_name(fund_name):
    """Look up fund data from the sheet."""
    funds = get_all_funds()
    for f in funds:
        if f.get("Fund Name", "").strip().lower() == fund_name.strip().lower():
            return f
    return None

def list_available_funds():
    """Returns list of fund names available for simulation."""
    funds = get_all_funds()
    return [f["Fund Name"] for f in funds if f.get("Fund Name")]

def run_pitch_session(mode="archetype", fund_name=None, archetype_key=None):
    """
    Interactive pitch practice session.
    mode: "archetype" (use predefined type) or "fund" (use specific fund from sheet)
    """
    if not config.GEMINI_API_KEY:
        print("No Gemini API key set in config.py. Add your key first.")
        return

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Build persona
    if mode == "archetype":
        if not archetype_key:
            print("Available archetypes:")
            for key, val in ARCHETYPES.items():
                print(f"  {key}: {val['description']}")
            archetype_key = input("\nChoose archetype: ").strip()
        system_prompt = build_persona_prompt(archetype_key=archetype_key)
        persona_label = f"{archetype_key} archetype"
    else:
        if not fund_name:
            print("Enter fund name (must match CSV exactly):")
            fund_name = input().strip()
        fund_data = get_fund_by_name(fund_name)
        if not fund_data:
            print(f"Fund '{fund_name}' not found in master.csv.")
            return
        system_prompt = build_persona_prompt(fund_data=fund_data)
        persona_label = fund_name

    print(f"\n{'='*60}")
    print(f"PITCH PRACTICE: {persona_label}")
    print("Type your pitch. Type 'quit' to end. Type 'feedback' for debrief.")
    print(f"{'='*60}\n")

    chat = client.chats.create(model="gemini-flash-latest")
    # Send system context as first message
    response = chat.send_message(system_prompt)
    print(f"Investor: {response.text}\n")

    conversation_log = []

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == 'quit':
            print("\nSession ended.")
            break
        if user_input.lower() == 'feedback':
            feedback_prompt = """Step out of the investor role for a moment.
            Give the founder honest, structured feedback on their pitch so far:
            1. What landed well
            2. What was weak or unclear
            3. The 2-3 specific things they must fix before the real meeting
            Be direct and specific."""
            response = chat.send_message(feedback_prompt)
            print(f"\n[DEBRIEF]\n{response.text}\n")
            continue

        conversation_log.append(("founder", user_input))
        response = chat.send_message(user_input)
        print(f"\nInvestor: {response.text}\n")
        conversation_log.append(("investor", response.text))

    return conversation_log

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "archetype"
    run_pitch_session(mode=mode)
