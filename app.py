import streamlit as st
import os
from pipeline import run_pipeline

# Check for API key from secrets or environment
def get_api_key():
    # Try Streamlit secrets first
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key is not None:
            return key
    except:
        pass
    # Fallback to environment
    return os.environ.get("GEMINI_API_KEY")

api_key = get_api_key()

# Validate API key: not empty, not starting with "your_"
def is_valid_key(key):
    if not key:
        return False
    if isinstance(key, str) and key.strip() == "":
        return False
    if isinstance(key, str) and key.strip().startswith("your_"):
        return False
    return True

if not is_valid_key(api_key):
    st.error("No API key set")
    st.stop()

# Set up the page
st.set_page_config(page_title="DischargeGuard", layout="wide")

# Safety banner at the top (from config.toml we'll set theme, but we can also show a warning)
st.warning("**Decision-support only. A clinician must approve before patient use.**")

# Title and subtitle
st.title("DischargeGuard")
st.caption("Turn discharge notes into a verified Marathi checklist, and catch unsafe gaps before the patient leaves.")

# Sample buttons
col1, col2, col3 = st.columns(3)
if col1.button("Load Trap Sample"):
    with open('samples/good_with_traps.txt', 'r') as f:
        st.session_state.note = f.read()
if col2.button("Load Too Vague Sample"):
    with open('samples/too_vague.txt', 'r') as f:
        st.session_state.note = f.read()
if col3.button("Load Appendectomy Sample"):
    st.session_state.note = "Patient discharged after appendectomy. Take Cefixime 200 mg twice daily for 5 days. Avoid heavy lifting. Come back if fever develops."

# Text area for discharge note
if 'note' not in st.session_state:
    st.session_state.note = ""
note = st.text_area("Enter discharge note:", value=st.session_state.note, height=200)

# Run pipeline button
if st.button("Run Pipeline"):
    if note.strip() == "":
        st.warning("Please enter a discharge note.")
    else:
        with st.spinner("Extracting and verifying instructions..."):
            result, debug = run_pipeline(note)

        if not result.can_generate:
            st.error(f"Cannot generate output: {result.refusal_reason}")
        else:
            # Hero metric
            st.metric(label="Safety issues caught before discharge", value=result.hero_metric)

            # Red panel: Ask the doctor before leaving
            st.subheader("⚠️ Ask the Doctor Before Leaving")
            if result.red_panel_items:
                for item in result.red_panel_items:
                    # Determine the issue type and message
                    issue_parts = []
                    if item.status != "clear":
                        issue_parts.append(f"Status: {item.status}")
                    if item.drift:
                        issue_parts.append("Drift detected")
                    if item.marathi_invalid:
                        issue_parts.append("Marathi validation failed")
                    issue = ", ".join(issue_parts) if issue_parts else "Unknown issue"
                    # Why it matters: we can give a generic message
                    st.error(f"**{issue}**")
                    st.markdown(f"*Why it matters:* This item may need clarification before discharge.")
                    st.markdown(f"*Source quote:* _{item.source_quote}_")
                    st.markdown("---")
            else:
                st.success("No issues found!")

            # Marathi checklist
            st.subheader("Marathi Checklist")
            for item in result.checklist:
                with st.container():
                    # We'll use columns for layout? We'll just use markdown with HTML for font size and color.
                    # Marathi text large (22px) using CSS font "Noto Sans Devanagari" with a fallback
                    # We'll use inline CSS for simplicity.
                    st.markdown(f"<div style=\"font-family: 'Noto Sans Devanagari\", sans-serif; font-size: 22px;\">{item.marathi}</div>", unsafe_allow_html=True)
                    st.markdown(f"<small style='color: grey;'>{item.english}</small>", unsafe_allow_html=True)
                    # Type badge: we need to determine type from instruction? We'll skip for now, or we can infer from keywords.
                    # We'll put a placeholder badge.
                    st.markdown("**Type:** Medicine")  # Placeholder
                    # Expander for source and verification
                    with st.expander("Source and verification"):
                        st.markdown(f"**Source quote:** _{item.source_quote}_")
                        # We need to get the back-translation and drift/Marathi warnings from debug.
                        # We'll need to map item to debug info. We'll skip for now and show placeholder.
                        st.markdown("*Back-translation:* [debug info not shown in this version]")
                        st.markdown("*Drift:* [debug info not shown]")
                        st.markdown("*Marathi validation:* [debug info not shown]")
                    # Verified tag
                    # We'll check if item passed validation (no drift, no marathi_invalid, and status clear?)
                    # We'll just show a green tag if status is clear and no drift and no marathi_invalid.
                    # We don't have easy access to those flags here; we'll skip.
                    st.markdown("---")

            # Teach-back quiz
            st.subheader("Marathi Teach-Back Quiz")
            quiz = result.teach_back_quiz
            if quiz.questions:
                st.write("Answer the following questions in Marathi:")
                for i, q in enumerate(quiz.questions):
                    st.markdown(f"**Q{i+1}:** {q.question}")
                    # Display options as radio buttons
                    options = q.options
                    choice = st.radio(f"Select answer for Q{i+1}:", options, key=f"q{i}")
                if st.button("Check answers"):
                    st.write("Answer checking not implemented in this version.")
            else:
                st.info("No quiz generated.")

            # Debug expander at the very bottom
            with st.expander("Debug Information", expanded=False):
                st.write(f"**Mode:** live")
                st.write(f"**Model:** {os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}")
                st.write(f"**Raw model response:** {debug.get('raw_response')}")
                st.write(f"**Items parsed (instructions):** {debug.get('items_parsed')}")
                st.write(f"**Items after verify:** {debug.get('items_after_verify')}")
                st.write(f"**Dropped items (unverifiable):** {debug.get('dropped_items')}")
                st.write(f"**Translation info:** {debug.get('translation_info')}")
                st.write(f"**Back-translation info:** {debug.get('back_translation_info')}")
                st.write(f"**Drift flags:** {debug.get('drift_flags')}")
                st.write(f"**Meaning match results:** {debug.get('meaning_match_results')}")
                st.write(f"**Marathi validation flags:** {debug.get('marathi_validation_flags')}")

# Footer
st.markdown("---")
st.markdown("*Built for hackathon demo. Synthetic data only.*")