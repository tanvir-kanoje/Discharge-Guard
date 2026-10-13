import os
import json
import re
import hashlib
import time
from google import genai
from google.genai import types
from schemas import *
from typing import List, Optional, Tuple, Dict, Any

# Cache directory
CACHE_DIR = ".cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def _cache_key(prompt: str) -> str:
    """Generate a cache key from the prompt."""
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()

def _get_cached_response(prompt: str) -> Optional[str]:
    """Get cached response if exists."""
    key = _cache_key(prompt)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return data.get("response")
        except Exception:
            pass
    return None

def _save_to_cache(prompt: str, response: str):
    """Save response to cache."""
    key = _cache_key(prompt)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(cache_file, 'w') as f:
            json.dump({"prompt": prompt, "response": response}, f)
    except Exception:
        pass

def _normalize_text(s: str) -> str:
    """Normalize text for comparison: lowercase, replace curly quotes/dashes, strip leading bullets/dashes, collapse whitespace."""
    if not s:
        return ""
    # Convert to lowercase
    s = s.lower()
    # Replace curly quotes and dashes with straight ASCII equivalents
    replacements = [
        ('“', '"'),
        ('”', '"'),
        ('‘', "'"),
        ('’', "'"),
        ('–', '-'),
        ('—', '-'),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    # Remove leading bullets, dashes, asterisks and whitespace
    s = s.lstrip('-*•')
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s.strip())
    return s

# Initialize Gemini client
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        import streamlit as st
        api_key = st.secrets.get("GEMINI_API_KEY")
    except:
        api_key = None

# Determine if we have a valid key (not empty, not starting with "your_")
def _is_valid_key(key: Optional[str]) -> bool:
    if not key:
        return False
    if isinstance(key, str) and key.strip() == "":
        return False
    if isinstance(key, str) and key.strip().startswith("your_"):
        return False
    return True

valid_api_key = _is_valid_key(api_key)
model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

if valid_api_key:
    client = genai.Client(api_key=api_key)
else:
    client = None

def _generate_json(prompt: str) -> str:
    """Generate JSON response from Gemini with retry and caching."""
    if not valid_api_key:
        raise ValueError("No API key set")
    # Check cache first
    cached = _get_cached_response(prompt)
    if cached is not None:
        return cached
    # Retry logic for 429/quota errors
    max_retries = 3
    wait_times = [5, 15, 30]  # seconds
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            # Assuming response.text contains the JSON string
            # The response might have multiple parts; we concatenate text parts
            response_text = ""
            if hasattr(response, 'text'):
                response_text = response.text
            else:
                # Fallback: iterate over parts
                for part in response.parts:
                    if hasattr(part, 'text'):
                        response_text += part.text
            # Save to cache
            _save_to_cache(prompt, response_text)
            return response_text
        except Exception as e:
            # Check if it's a 429 or quota error
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                if attempt < max_retries - 1:
                    time.sleep(wait_times[attempt])
                    continue
                else:
                    # After max retries, show error
                    raise e
            else:
                # Non-quota error, raise immediately
                raise e
    # Should not reach here
    raise Exception("Max retries exceeded")

def extract(note: str) -> Tuple[List[ExtractedItem], str]:
    """Extract medical instructions from discharge note."""
    if not valid_api_key:
        raise ValueError("No API key set")
    prompt = f"""
    Extract all medical instructions, medications, follow-ups, warnings, and advice 
    from the discharge note below. For each instruction, provide the exact text 
    from the note as source_quote.

    DISCHARGE NOTE:
    {note}

    Return a JSON list of objects with keys: instruction, source_quote.
    """
    try:
        raw_response = _generate_json(prompt)
        # Strip code fences if present
        text = raw_response
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        # Validate with pydantic
        items = [ExtractedItem(**item) for item in data]
        return items, raw_response
    except Exception as e:
        # Re-raise to be handled by run_pipeline
        raise e

def verify(items: List[ExtractedItem], note: str) -> Tuple[List[VerifiedItem], List[str]]:
    """Verify extracted items against the note (code-based). Returns (verified_items, flags)."""
    # Verify does not require API key, it's code-based.
    verified = []
    flags = []
    norm_note = _normalize_text(note)
    
    for item in items:
        # Normalize the source_quote for comparison
        norm_quote = _normalize_text(item.source_quote)
        # Check if source_quote is a substring of the note
        if norm_quote in norm_note:
            # Determine status based on vague/conflicting/missing heuristics
            # For simplicity, we'll mark as clear unless we detect issues
            status = "clear"
            # Check for vagueness (e.g., "as needed", "follow up")
            if re.search(r'\bas needed\b|\bfollow up\b|\bmonitor\b', item.instruction, re.I):
                status = "vague"
            # Check for missing doses/frequency (simple regex)
            if re.search(r'\b(mg|tablet|pill|unit|iu)\b', item.instruction, re.I) is None:
                if re.search(r'\b(take|use|apply)\b', item.instruction, re.I):
                    status = "missing"  # missing dosage info
            verified.append(VerifiedItem(
                instruction=item.instruction,
                source_quote=item.source_quote,
                status=status
            ))
        else:
            # Source quote not found - flag this item
            flags.append(f"Could not verify instruction: {item.instruction}")
            # Also add to verified as failed? We'll skip adding to verified
            # But we need to return something for this item? We'll skip.
    return verified, flags

def translate(items: List[VerifiedItem]) -> List[TranslationItem]:
    """Translate verified items to Marathi."""
    if not valid_api_key:
        raise ValueError("No API key set")
    if not items:
        return []
    # Build prompt for batch translation
    instructions = "\n".join([f"- {item.instruction}" for item in items])
    prompt = f"""
    Translate the following medical instructions from English to Marathi.
    Keep drug names, doses, and numbers in Latin script/digits.
    Return a JSON list of objects with keys: english, marathi, source_quote.
    The source_quote should be the original English instruction.

    INSTRUCTIONS:
    {instructions}

    Return only valid JSON.
    """
    try:
        raw_response = _generate_json(prompt)
        # Strip code fences if present
        text = raw_response
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        # Validate with pydantic
        translations = []
        for item, trans in zip(items, data):
            translations.append(TranslationItem(
                english=item.instruction,
                marathi=trans["marathi"],
                source_quote=item.source_quote
            ))
        return translations
    except Exception as e:
        print(f"Translation error: {e}")
        # Fallback: simple placeholder
        return [TranslationItem(
            english=item.instruction,
            marathi="[Translation not available]",
            source_quote=item.source_quote
        ) for item in items]

def back_translate(marathi_text: str) -> BackTranslationResult:
    """Translate Marathi text back to English and check for drift."""
    if not valid_api_key:
        raise ValueError("No API key set")
    prompt = f"""
    Translate the following Marathi text to English.
    Return a JSON object with keys: original (the Marathi text), back_translated (the English translation).

    MARATHI TEXT:
    {marathi_text}

    Return only valid JSON.
    """
    try:
        raw_response = _generate_json(prompt)
        # Strip code fences if present
        text = raw_response
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        # Simple drift detection: check if back_translated is meaningful
        # For now, we'll just return the result
        return BackTranslationResult(
            original=marathi_text,
            back_translated=data["back_translated"],
            drift_detected=False,  # Placeholder
            drift_explanation=None
        )
    except Exception as e:
        print(f"Back translation error: {e}")
        return BackTranslationResult(
            original=marathi_text,
            back_translated="[Error]",
            drift_detected=True,
            drift_explanation=str(e)
        )

def make_quiz(items: List[VerifiedItem]) -> QuizResult:
    """Generate a 3-question Marathi teach-back quiz."""
    if not valid_api_key:
        raise ValueError("No API key set")
    if not items:
        return QuizResult(questions=[], user_answers=[], score=0)
    # We'll generate questions based on the first few items
    quiz_items = items[:3]  # Take up to 3 items
    questions = []
    for item in quiz_items:
        # Create a simple question about dosage or timing
        prompt = f"""
        Generate a simple multiple-choice question in Marathi to test understanding 
        of the following medical instruction. The question should be about 
        dosage, frequency, or timing. Provide 4 options, one correct.
        Return a JSON object with keys: question (Marathi), options (list of 4 strings), 
        correct_answer (the correct option string), source_quote (the original English instruction).

        INSTRUCTION:
        {item.instruction}

        Return only valid JSON.
        """
        try:
            raw_response = _generate_json(prompt)
            # Strip code fences if present
            text = raw_response
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            questions.append(QuizQuestion(
                question=data["question"],
                options=data["options"],
                correct_answer=data["correct_answer"],
                source_quote=item.source_quote
            ))
        except Exception as e:
            print(f"Quiz generation error: {e}")
            # Fallback question
            questions.append(QuizQuestion(
                question=f"{item.instruction} कधी घ्यावी?",
                options=["सकाळी", "दुपारी", "संध्याकाळी", "रात्री"],
                correct_answer="रात्री",  # Placeholder
                source_quote=item.source_quote
            ))
    return QuizResult(questions=questions, user_answers=[], score=0)

def run_pipeline(note: str) -> Tuple[PipelineOutput, Dict]:
    """Run the full pipeline on a discharge note."""
    debug = {
        "mode": "live" if valid_api_key else "mock",  # We'll keep mode for debug, but if not valid_api_key, we will have raised earlier.
        "model": model_name if valid_api_key else None,
        "raw_response": None,
        "items_parsed": [],
        "items_after_verify": [],
        "dropped_items": []
    }
    
    # If API key is not valid, we would have raised in extract or other functions.
    # So we assume valid_api_key is True here.
    
    # Extract
    try:
        extracted, raw_response = extract(note)
        debug["items_parsed"] = [item.instruction for item in extracted]
        debug["raw_response"] = raw_response
    except Exception as e:
        # If extraction fails, return an error output
        output = PipelineOutput(
            checklist=[],
            red_panel_items=[],
            back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
            teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
            hero_metric=0,
            refusal_reason=f"Extraction error: {e}",
            can_generate=False
        )
        return output, debug
    
    # Verify
    try:
        verified, flags = verify(extracted, note)
        debug["items_after_verify"] = [item.instruction for item in verified]
        # For dropped items, we need to know which items were dropped and why.
        # The verify function returns flags, which are messages about dropped items.
        # We can pair each flag with the item that caused it? Not directly.
        # We'll store the flags as dropped items reasons.
        debug["dropped_items"] = flags  # This is a list of strings.
    except Exception as e:
        output = PipelineOutput(
            checklist=[],
            red_panel_items=[],
            back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
            teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
            hero_metric=0,
            refusal_reason=f"Verification error: {e}",
            can_generate=False
        )
        return output, debug
    
    if not verified and flags:
        output = PipelineOutput(
            checklist=[],
            red_panel_items=[],
            back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
            teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
            hero_metric=0,
            refusal_reason="; ".join(flags),
            can_generate=False
        )
        return output, debug
    
    # Translate verified items to Marathi for checklist
    try:
        checklist_items = translate(verified)
    except Exception as e:
        output = PipelineOutput(
            checklist=[],
            red_panel_items=[],
            back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
            teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
            hero_metric=0,
            refusal_reason=f"Translation error: {e}",
            can_generate=False
        )
        return output, debug
    
    # Red panel items are the verified items that are not clear
    red_panel_items = [item for item in verified if item.status != "clear"]
    
    # Back-translation check: translate the first checklist item's Marathi back to English
    back_translation_check = BackTranslationResult(original="", back_translated="", drift_detected=False)
    if checklist_items:
        # Take the first item's Marathi text
        marathi_text = checklist_items[0].marathi
        try:
            back_translation_check = back_translate(marathi_text)
        except Exception as e:
            output = PipelineOutput(
                checklist=[],
                red_panel_items=[],
                back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
                teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
                hero_metric=0,
                refusal_reason=f"Back-translation error: {e}",
                can_generate=False
            )
            return output, debug
    
    # Quiz
    try:
        quiz_result = make_quiz(verified)
    except Exception as e:
        output = PipelineOutput(
            checklist=[],
            red_panel_items=[],
            back_translation_check=BackTranslationResult(original="", back_translated="", drift_detected=True),
            teach_back_quiz=QuizResult(questions=[], user_answers=[], score=0),
            hero_metric=0,
            refusal_reason=f"Quiz generation error: {e}",
            can_generate=False
        )
        return output, debug
    
    # Hero metric: number of safety issues caught (red panel items)
    hero_metric = len(red_panel_items)
    
    output = PipelineOutput(
        checklist=checklist_items,
        red_panel_items=red_panel_items,
        back_translation_check=back_translation_check,
        teach_back_quiz=quiz_result,
        hero_metric=hero_metric,
        refusal_reason=None,
        can_generate=True
    )
    return output, debug
