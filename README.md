# DischargeGuard

A patient-safety verifier for hospital discharge notes in India.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Anthropic API key in Streamlit secrets or as an environment variable:
   ```bash
   export ANTHROPIC_API_KEY=your_key_here
   ```
   Or in `.streamlit/secrets.toml`:
   ```toml
   ANTHROPIC_API_KEY = "your_key_here"
   ```

## Run Locally
```bash
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
1. Push to GitHub
2. Go to share.streamlit.io
3. Connect your repo
4. Set the secret `ANTHROPIC_API_KEY`
5. Deploy

## Project Structure
- `app.py`: Streamlit UI
- `pipeline.py`: Core pipeline (extract, verify, translate, back_translate, make_quiz)
- `schemas.py`: Pydantic models
- `samples/`: Sample discharge notes
- `test_pipeline.py`: Tests for the pipeline
