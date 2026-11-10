import streamlit as st
import os
from pipeline import run_pipeline, extract_text_from_media
from PIL import Image
import io

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="DischargeGuard | Clinical Safety & Localization",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# Modern, Soft Healthcare CSS Styling
# ---------------------------------------------------------
st.markdown("""
<style>
    /* Global Font & Smooth Reset */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #1E293B;
    }
    
    /* Main Background: Soft Serene Sky Tint */
    .stApp {
        background: linear-gradient(180deg, #F8FAFC 0%, #F0F9FF 100%);
    }

    /* Soft Header Banner: Soothing Cool Tones (Serene Blue to Healing Mint) */
    .hero-container {
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 35%, #ECFDF5 70%, #F0FDF4 100%);
        border: 1px solid #BAE6FD;
        border-radius: 20px;
        padding: 28px 34px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px -4px rgba(2, 132, 199, 0.08);
    }
    
    .hero-title {
        font-size: 32px;
        font-weight: 700;
        color: #0369A1;
        letter-spacing: -0.5px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-subtitle {
        font-size: 15px;
        color: #334155;
        margin-top: 8px;
        line-height: 1.55;
    }

    /* Clinical Decision Support Banner: Calming Serene Sky & Mint */
    .clinical-banner {
        background: #F0F9FF;
        border: 1px solid #BAE6FD;
        border-radius: 12px;
        padding: 11px 18px;
        font-size: 13.5px;
        color: #0369A1;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 24px;
        box-shadow: 0 2px 8px -2px rgba(2, 132, 199, 0.04);
    }

    /* Soft Cards with Serene Accent */
    .card-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 18px;
        box-shadow: 0 2px 12px -2px rgba(2, 132, 199, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .card-box:hover {
        box-shadow: 0 6px 18px -2px rgba(2, 132, 199, 0.08);
    }

    /* Red Panel Alert Cards: Soft Rose-Coral for Calm Clinical Attention */
    .red-panel-card {
        background: #FFF1F2;
        border: 1px solid #FECDD3;
        border-left: 5px solid #E11D48;
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px -2px rgba(225, 29, 72, 0.05);
    }

    .red-panel-badge {
        background: #FFE4E6;
        color: #BE123C;
        font-size: 11.5px;
        font-weight: 700;
        text-transform: uppercase;
        padding: 3px 9px;
        border-radius: 6px;
        letter-spacing: 0.5px;
        display: inline-block;
        margin-bottom: 8px;
    }

    /* Checklist Card: Healing Mint Left Border */
    .checklist-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #10B981;
        border-radius: 16px;
        padding: 20px 22px;
        margin-bottom: 16px;
        box-shadow: 0 2px 10px -2px rgba(16, 185, 129, 0.04);
    }

    .devanagari-text {
        font-family: 'Noto Sans Devanagari', sans-serif;
        font-size: 22px;
        font-weight: 600;
        color: #0F172A;
        line-height: 1.45;
        margin-bottom: 6px;
    }

    .english-subtext {
        font-size: 14.5px;
        color: #64748B;
        font-weight: 400;
    }

    .source-quote-box {
        background: #F0F9FF;
        border: 1px dashed #BAE6FD;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 12.5px;
        color: #0369A1;
        font-style: italic;
        margin-top: 10px;
    }

    /* Metric Badges: Serene Blue & Healing Green */
    .metric-badge-container {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }

    .metric-tile {
        flex: 1;
        min-width: 220px;
        background: #FFFFFF;
        border: 1px solid #E0F2FE;
        border-radius: 14px;
        padding: 16px 20px;
        box-shadow: 0 2px 10px -2px rgba(2, 132, 199, 0.04);
    }

    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: #0284C7;
    }

    .metric-lbl {
        font-size: 13px;
        color: #64748B;
        font-weight: 500;
        margin-top: 4px;
    }

    /* Pill Badges */
    .badge-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-clear { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .badge-vague { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
    .badge-missing { background: #FEE2E2; color: #B91C1C; border: 1px solid #FECDD3; }

    /* Button Styling: Serene Cerulean Blue */
    div.stButton > button {
        border-radius: 12px;
        font-weight: 600;
        font-size: 15px;
        padding: 10px 24px;
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="primary"] {
        background-color: #0284C7;
        border-color: #0284C7;
        color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0369A1;
        border-color: #0369A1;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.28);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# API Key Verification & Fallback Helper
# ---------------------------------------------------------
def get_api_key():
    # 1. Try Streamlit secrets
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    # 2. Try Environment variable
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
    # 3. Try Session state
    return st.session_state.get("user_gemini_key", "")

def is_valid_key(key):
    if not key:
        return False
    if isinstance(key, str) and (key.strip() == "" or key.strip().startswith("your_")):
        return False
    return True

api_key = get_api_key()

# ---------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛡️ DischargeGuard")
    st.caption("AI-Powered Hospital Discharge Gatekeeper")
    st.markdown("---")
    
    # API Key Input if not already detected
    if not is_valid_key(api_key):
        st.warning("⚠️ Gemini API Key Required")
        user_key = st.text_input("Enter Gemini API Key:", type="password", placeholder="AIzaSy...")
        if user_key:
            st.session_state.user_gemini_key = user_key
            st.rerun()
        st.info("💡 Get a free key at [Google AI Studio](https://aistudio.google.com/) (100% Free Tier, no credit card required).")
    else:
        st.success("✅ Gemini API Connected")
        st.caption("Model: `gemini-2.5-flash` (Multimodal Free Tier)")
    
    st.markdown("---")
    st.markdown("#### ⚙️ Pipeline Features")
    st.markdown("- 📸 **Cloud Vision OCR** (Photos/PDFs)")
    st.markdown("- 🔍 **English Clinical Verification**")
    st.markdown("- ⚠️ **Red Panel Safety Gate**")
    st.markdown("- 🌐 **Marathi & Hindi Localization**")
    st.markdown("- 🔄 **Zero-Drift Back-Translation**")
    st.markdown("- 🎓 **Interactive Teach-Back Quiz**")
    
    st.markdown("---")
    st.caption("v2.0 • Built for RBU Google Hackathon")

# Check if we should block execution for missing key
if not is_valid_key(api_key):
    st.error("Please enter a valid Gemini API key in the sidebar or set `GEMINI_API_KEY` in Streamlit secrets to proceed.")
    st.stop()

# ---------------------------------------------------------
# Hero Banner
# ---------------------------------------------------------
st.markdown("""
<div class="hero-container">
    <h1 class="hero-title">🛡️ DischargeGuard</h1>
    <div class="hero-subtitle">
        Turn complex English discharge summaries and physical doctor prescriptions into verified, 
        zero-hallucination checklists in <b>Marathi</b> & <b>Hindi</b>, and catch life-threatening safety gaps before the patient walks out.
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="clinical-banner">
    <span>⚕️</span>
    <span><b>Clinical Decision Support:</b> Attending clinician review and approval required before patient discharge hand-off.</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Ingestion Layer: Cloud Vision OCR, Upload, Camera & Text
# ---------------------------------------------------------
st.markdown("### 📄 1. Prescription & Discharge Note Ingestion")

# Initialize session state for the note
if 'note' not in st.session_state:
    st.session_state.note = ""

# Ingestion Tabs
tab_upload, tab_camera, tab_text, tab_samples = st.tabs([
    "📁 Upload Prescription (Image/PDF)", 
    "📷 Camera Capture", 
    "✍️ Type or Paste Text", 
    "🧪 Quick Test Samples"
])

# Tab 1: File Uploader (Cloud Vision OCR)
with tab_upload:
    st.markdown("Upload a photo or scanned PDF of a physical doctor's prescription or hospital discharge summary.")
    uploaded_file = st.file_uploader(
        "Choose prescription file",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        help="Supports JPG, PNG, WEBP, and scanned PDF discharge summaries."
    )
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type or "image/jpeg"
        
        col_prev, col_act = st.columns([1, 1])
        with col_prev:
            if mime_type.startswith("image/"):
                try:
                    img = Image.open(io.BytesIO(file_bytes))
                    st.image(img, caption=f"Uploaded: {uploaded_file.name}", use_container_width=True)
                except Exception:
                    st.info(f"File: {uploaded_file.name} ({len(file_bytes)} bytes)")
            else:
                st.info(f"📄 PDF Document: **{uploaded_file.name}** ({round(len(file_bytes)/1024, 1)} KB)")

        with col_act:
            st.markdown("#### Cloud Vision OCR")
            st.caption("Gemini 2.5 Flash will transcribe printed medical text, tables, and handwritten doctor notes.")
            if st.button("🔍 Extract Text with Cloud Vision", key="btn_ocr_upload", type="primary"):
                with st.spinner("Extracting English medical text with Gemini Cloud Vision..."):
                    try:
                        transcribed_text = extract_text_from_media(file_bytes, mime_type=mime_type)
                        st.session_state.note = transcribed_text
                        st.success("✅ Extraction complete! Text loaded into review editor.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"OCR Error: {e}")

# Tab 2: Live Camera Capture
with tab_camera:
    st.markdown("Use your smartphone or webcam to take an instant photo of the physical prescription.")
    camera_photo = st.camera_input("Take photo of discharge paper")
    if camera_photo is not None:
        cam_bytes = camera_photo.getvalue()
        if st.button("🔍 Extract Text from Photo", key="btn_ocr_cam", type="primary"):
            with st.spinner("Transcribing photo with Gemini Cloud Vision..."):
                try:
                    transcribed_text = extract_text_from_media(cam_bytes, mime_type="image/jpeg")
                    st.session_state.note = transcribed_text
                    st.success("✅ Photo transcribed! Text loaded into review editor.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Camera OCR Error: {e}")

# Tab 3: Direct Text Input
with tab_text:
    st.markdown("Type or paste raw English discharge summary text directly.")

# Tab 4: Pre-loaded Clinical Test Samples
with tab_samples:
    st.markdown("Click any sample below to load synthetic test scenarios:")
    col_s1, col_s2, col_s3 = st.columns(3)
    if col_s1.button("⚠️ Load Note with Safety Traps"):
        try:
            with open('samples/good_with_traps.txt', 'r') as f:
                st.session_state.note = f.read()
            st.rerun()
        except Exception as e:
            st.error(f"Could not load sample: {e}")

    if col_s2.button("🚫 Load Too Vague Sample (Refusal)"):
        try:
            with open('samples/too_vague.txt', 'r') as f:
                st.session_state.note = f.read()
            st.rerun()
        except Exception as e:
            st.error(f"Could not load sample: {e}")

    if col_s3.button("✅ Load Appendectomy (Clean)"):
        st.session_state.note = (
            "Patient Name: Rahul Verma, Age: 34\n"
            "Diagnosis: Acute Appendicitis s/p Laparoscopic Appendectomy\n"
            "Discharge Medications:\n"
            "- Cefixime 200mg twice daily for 5 days after food\n"
            "- Paracetamol 650mg SOS for fever or surgical pain (max 3 times daily)\n"
            "- Pantoprazole 40mg once daily before breakfast for 5 days\n"
            "Instructions:\n"
            "- Keep surgical incision dry for 48 hours\n"
            "- Avoid heavy lifting (>5 kg) for 3 weeks\n"
            "- Return to emergency if persistent high fever (>101°F) or wound redness occurs\n"
            "- OPD Review with surgeon after 7 days for suture check"
        )
        st.rerun()

# ---------------------------------------------------------
# Verified English Note Editor
# ---------------------------------------------------------
st.markdown("---")
st.markdown("#### 📝 English Clinical Text (Ground Truth)")
st.caption("Review or edit the English prescription before running the safety gatekeeper.")

note = st.text_area(
    label="English Discharge Summary",
    value=st.session_state.note,
    height=210,
    placeholder="Prescription text will appear here automatically upon OCR extraction, or you can paste text directly..."
)

col_run, col_clear = st.columns([3, 1])
with col_run:
    run_btn = st.button("⚡ Run Clinical Safety Pipeline", type="primary", use_container_width=True)
with col_clear:
    if st.button("🗑️ Clear Note", use_container_width=True):
        st.session_state.note = ""
        st.rerun()

# ---------------------------------------------------------
# Pipeline Execution & Results
# ---------------------------------------------------------
if run_btn:
    if not note.strip():
        st.warning("⚠️ Please provide or extract a discharge note first.")
    else:
        with st.spinner("Auditing safety gaps, verifying instructions, and localizing into Marathi & Hindi..."):
            try:
                result, debug = run_pipeline(note)
                st.session_state.pipeline_result = result
                st.session_state.pipeline_debug = debug
            except Exception as e:
                st.error(f"Pipeline Execution Failed: {e}")

# Render results from session state if available
if "pipeline_result" in st.session_state:
    result = st.session_state.pipeline_result
    debug = st.session_state.get("pipeline_debug", {})

    st.markdown("---")

    # Safety Refusal Gate
    if not result.can_generate:
        st.markdown(f"""
        <div class="red-panel-card" style="border-left-color: #BE123C; background: #FFF1F2;">
            <div class="red-panel-badge">🛑 Critical Safety Refusal</div>
            <h3 style="color: #9F1239; margin-top: 4px;">Discharge Checklist Generation Blocked</h3>
            <p style="color: #4C0519; font-size: 15px;"><b>Reason:</b> {result.refusal_reason}</p>
            <p style="color: #881337; font-size: 13.5px;">
                <i>DischargeGuard refused generation because this discharge note is missing essential clinical orders or is too vague to safely protect the patient at home. Please have the clinician provide explicit medication doses and follow-up directives.</i>
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Hero Metrics Dashboard
        st.markdown("### 📊 Clinical Safety Dashboard")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-val" style="color: {'#E11D48' if result.hero_metric > 0 else '#059669'};">
                    {result.hero_metric}
                </div>
                <div class="metric-lbl">Safety Gaps & Traps Caught</div>
            </div>
            """, unsafe_allow_html=True)

        with col_m2:
            verified_count = len(result.checklist)
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-val" style="color: #059669;">{verified_count}</div>
                <div class="metric-lbl">Verified Safe Clinical Orders</div>
            </div>
            """, unsafe_allow_html=True)

        with col_m3:
            drift_status = "0% Drift" if not result.back_translation_check.drift_detected else "Drift Caught"
            drift_color = "#059669" if not result.back_translation_check.drift_detected else "#D97706"
            st.markdown(f"""
            <div class="metric-tile">
                <div class="metric-val" style="color: {drift_color};">{drift_status}</div>
                <div class="metric-lbl">Back-Translation Integrity</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # The Red Panel: Action Required
        # ---------------------------------------------------------
        if result.red_panel_items:
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                <h3 style="color: #BE123C; margin: 0;">⚠️ Ask the Doctor Before Leaving (Red Panel)</h3>
            </div>
            <p style="color: #475569; font-size: 14px; margin-bottom: 16px;">
                These instructions contain ambiguities, missing dosages, or potential risks that require clarification from the attending physician before discharge.
            </p>
            """, unsafe_allow_html=True)

            for item in result.red_panel_items:
                status_label = item.status.upper()
                badge_class = "badge-vague" if item.status == "vague" else "badge-missing"
                
                extra_flags = []
                if item.drift:
                    extra_flags.append("Meaning Drift Detected")
                if item.marathi_invalid:
                    extra_flags.append("Script Validation Failed")
                extra_str = f" | {', '.join(extra_flags)}" if extra_flags else ""

                st.markdown(f"""
                <div class="red-panel-card">
                    <span class="badge-pill {badge_class}">{status_label}{extra_str}</span>
                    <h4 style="color: #881337; margin: 6px 0 4px 0;">{item.instruction}</h4>
                    <p style="color: #9F1239; font-size: 13.5px; margin-bottom: 8px;">
                        <b>Clinical Note:</b> This directive lacks critical details (e.g. exact timing, max dosage, or milestone) which could lead to post-discharge errors.
                    </p>
                    <div class="source-quote-box">
                        <b>Source in note:</b> "{item.source_quote}"
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ **No Clinical Ambiguities Detected:** All instructions passed safety checks with zero unverified items.")

        st.markdown("---")

        # ---------------------------------------------------------
        # Patient-Facing Localized Checklist
        # ---------------------------------------------------------
        st.markdown("### 📋 Patient Vernacular Discharge Checklist")
        st.caption("All drug names, dosages, and units remain in English/Latin script on medicine strips for patient identification.")

        # Language Selection Tabs
        lang_choice = st.radio(
            "Select Patient Language:",
            ["मराठी (Marathi)", "हिंदी (Hindi)", "English Reference", "Dual Bilingual View"],
            horizontal=True
        )

        for idx, item in enumerate(result.checklist):
            hindi_text = getattr(item, 'hindi', None) or "[Hindi translation not available]"
            
            with st.container():
                st.markdown("""<div class="checklist-card">""", unsafe_allow_html=True)
                
                # Render according to language selection
                if lang_choice == "मराठी (Marathi)":
                    st.markdown(f'<div class="devanagari-text">{item.marathi}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="english-subtext">English: {item.english}</div>', unsafe_allow_html=True)
                elif lang_choice == "हिंदी (Hindi)":
                    st.markdown(f'<div class="devanagari-text">{hindi_text}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="english-subtext">English: {item.english}</div>', unsafe_allow_html=True)
                elif lang_choice == "English Reference":
                    st.markdown(f'<div style="font-size: 19px; font-weight: 600; color: #0F172A; margin-bottom: 4px;">{item.english}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="english-subtext">मराठी: {item.marathi}</div>', unsafe_allow_html=True)
                else: # Dual View
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.markdown(f'<div class="devanagari-text" style="font-size: 20px;">{item.marathi}</div>', unsafe_allow_html=True)
                        st.caption("मराठी (Marathi)")
                    with col_d2:
                        st.markdown(f'<div class="devanagari-text" style="font-size: 20px;">{hindi_text}</div>', unsafe_allow_html=True)
                        st.caption("हिंदी (Hindi)")
                    st.markdown(f'<div class="english-subtext">Original: {item.english}</div>', unsafe_allow_html=True)

                # Verification & Source Expander
                with st.expander(f"🔍 Source Verification & Bounding Proof #{idx+1}"):
                    st.markdown(f"**Verbatim Source Quote:** `\"{item.source_quote}\"`")
                    st.markdown("✅ **Status:** Clinically Verified & Anchored to Source Document")

                st.markdown("""</div>""", unsafe_allow_html=True)

        st.markdown("---")

        # ---------------------------------------------------------
        # Interactive Teach-Back Patient Quiz
        # ---------------------------------------------------------
        st.markdown("### 🎓 Interactive Teach-Back Patient Comprehension Quiz")
        st.caption("Tests whether the patient or caregiver genuinely understood high-risk medication schedules and emergency warnings.")

        quiz = result.teach_back_quiz
        if quiz.questions:
            # Quiz submission state
            if "quiz_submitted" not in st.session_state:
                st.session_state.quiz_submitted = False

            user_choices = {}
            for i, q in enumerate(quiz.questions):
                st.markdown(f"""
                <div class="card-box" style="padding: 16px 20px; border-left: 4px solid #0D9488;">
                    <div style="font-family: 'Noto Sans Devanagari', sans-serif; font-size: 17px; font-weight: 600; color: #0F172A; margin-bottom: 8px;">
                        प्रश्न {i+1}: {q.question}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                user_choices[i] = st.radio(
                    f"पर्याय निवडा (Select answer for Q{i+1}):",
                    q.options,
                    key=f"quiz_opt_{i}"
                )

            if st.button("📝 Check Answers & Verify Comprehension", type="primary"):
                st.session_state.quiz_submitted = True
                correct_count = 0
                for i, q in enumerate(quiz.questions):
                    selected = user_choices.get(i)
                    if selected == q.correct_answer:
                        correct_count += 1
                        st.success(f"✅ **प्रश्न {i+1}: बरोबर उत्तर! (Correct)** — `{q.correct_answer}`")
                    else:
                        st.error(f"❌ **प्रश्न {i+1}: चुकीचे उत्तर (Incorrect).** योग्य उत्तर: **{q.correct_answer}** (Source: _{q.source_quote}_)")
                
                score_percent = round((correct_count / len(quiz.questions)) * 100)
                if score_percent == 100:
                    st.balloons()
                    st.success(f"🎉 **Comprehension Score: 100% ({correct_count}/{len(quiz.questions)})** — The patient/caregiver is ready for discharge hand-off!")
                else:
                    st.warning(f"⚠️ **Comprehension Score: {score_percent}% ({correct_count}/{len(quiz.questions)})** — Please have the nursing staff re-explain the missed items before discharge.")
        else:
            st.info("No teach-back quiz was needed for this note.")

        # ---------------------------------------------------------
        # Technical Audit & Debug Information
        # ---------------------------------------------------------
        with st.expander("🛠️ Technical Audit & Debug Trail (For Evaluators)", expanded=False):
            st.markdown(f"**Model In Use:** `{os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}`")
            st.markdown(f"**Back-Translation Drift Flag:** `{result.back_translation_check.drift_detected}`")
            if result.back_translation_check.drift_explanation:
                st.markdown(f"**Drift Explanation:** `{result.back_translation_check.drift_explanation}`")
            st.json({
                "hero_metric": result.hero_metric,
                "verified_items_count": len(result.checklist),
                "red_panel_items_count": len(result.red_panel_items),
                "dropped_unverifiable_items": debug.get("dropped_items", []),
                "drift_flags": debug.get("drift_flags", []),
                "marathi_validation_flags": debug.get("marathi_validation_flags", [])
            })

# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #94A3B8; font-size: 13px;">
    DischargeGuard • Google AI Hackathon Project • Synthetic Data Testing • Clinical Decision Support
</div>
""", unsafe_allow_html=True)
