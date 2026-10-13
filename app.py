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
st.set_page_config(page_title="DischargeGuard", layout="centered")

# Display banner
st.balloons()
st.markdown("""
# DischargeGuard
**Decision-support only. A clinician must approve before patient use.**
""")

# Load sample buttons
col1, col2 = st.columns(2)
if col1.button("Load Good Sample"):
    with open('samples/good_with_traps.txt', 'r') as f:
        st.session_state.note = f.read()
if col2.button("Load Too Vague Sample"):
    with open('samples/too_vague.txt', 'r') as f:
        st.session_state.note = f.read()

# Text area for discharge note
if 'note' not in st.session_state:
    st.session_state.note = ""
note = st.text_area("Enter discharge note:", value=st.session_state.note, height=200)

# Run pipeline button
if st.button("Run Pipeline"):
    if note.strip() == "":
        st.warning("Please enter a discharge note.")
    else:
        with st.spinner("Processing..."):
            result, debug = run_pipeline(note)
        
        if not result.can_generate:
            st.error(f"Cannot generate output: {result.refusal_reason}")
        else:
            # Display checklist
            st.subheader("Marathi Checklist")
            for item in result.checklist:
                st.markdown(f"**{item.english}**")
                st.markdown(f"*Marathi:* {item.marathi}")
                st.markdown(f"*Source:* _{item.source_quote}_")
                st.markdown("---")
            
            # Display red panel
            st.subheader("⚠️ Ask the Doctor Before Leaving")
            if result.red_panel_items:
                for item in result.red_panel_items:
                    st.markdown(f"**{item.instruction}**")
                    st.markdown(f"*Status:* {item.status}")
                    st.markdown(f"*Source:* _{item.source_quote}_")
                    st.markdown("---")
            else:
                st.success("No issues found!")
            
            # Display back-translation check
            st.subheader("Back-Translation Check")
            bt = result.back_translation_check
            st.markdown(f"**Original Marathi:** {bt.original}")
            st.markdown(f"**Back-translated English:** {bt.back_translated}")
            if bt.drift_detected:
                st.warning(f"Meaning drift detected: {bt.drift_explanation}")
            else:
                st.success("No significant meaning drift detected.")
            
            # Display quiz
            st.subheader("Marathi Teach-Back Quiz")
            quiz = result.teach_back_quiz
            if quiz.questions:
                st.write("Answer the following questions in Marathi:")
                for i, q in enumerate(quiz.questions):
                    st.markdown(f"**Q{i+1}:** {q.question}")
                    # Display options as radio buttons
                    options = q.options
                    # We'll use a key for each radio button
                    choice = st.radio(f"Select answer for Q{i+1}:", options, key=f"q{i}")
                    # Store the answer in session state for scoring (optional)
                    # For now, just display
                st.button("Submit Quiz")  # Placeholder
            else:
                st.info("No quiz generated.")
            
            # Display hero metric
            st.subheader("Hero Metric")
            st.metric(label="Safety issues caught before discharge", value=result.hero_metric)
            
            # Debug expander
            with st.expander("Debug Information"):
                st.write(f"**Mode:** live")
                st.write(f"**Model:** {os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}")
                st.write(f"**Raw model response:** {debug['raw_response']}")
                st.write(f"**Items parsed (instructions):** {debug['items_parsed']}")
                st.write(f"**Items after verify:** {debug['items_after_verify']}")
                st.write(f"**Dropped items (with reasons):** {debug['dropped_items']}")

# Footer
st.markdown("---")
st.markdown("*Built for hackathon demo. Synthetic data only.*")
