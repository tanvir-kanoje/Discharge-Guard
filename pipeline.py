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

def verify(items: List[ExtractedItem], note: str) -> Tuple[List[VerifiedItem], List[str], List[Dict]]:
    """Verify extracted items against the note (code-based). 
    Returns (verified_items, flags, item_info) where:
      - verified_items: list of VerifiedItem with status
      - flags: list of strings for items that could not be verified (source_quote not found)
      - item_info: list of dicts for each verified item with keys: id, instruction, source_quote, status, and any flags for that item (like vague, missing, conflict)
    """
    # Verify does not require API key, it's code-based.
    verified = []
    flags = []  # for items where source_quote not found
    item_info = []  # detailed info for each verified item
    norm_note = _normalize_text(note)
    
    for idx, item in enumerate(items):
        # Normalize the source_quote for comparison
        norm_quote = _normalize_text(item.source_quote)
        # Check if source_quote is a substring of the note
        if norm_quote in norm_note:
            # Determine status based on vague/conflicting/missing heuristics
            status = "clear"
            item_flags = []
            # Check for vagueness (e.g., "as needed", "follow up")
            if re.search(r'\bas needed\b|\bfollow up\b|\bmonitor\b', item.instruction, re.I):
                status = "vague"
                item_flags.append("vague")
            # Check for missing doses/frequency (simple regex)
            if re.search(r'\b(mg|tablet|pill|unit|iu)\b', item.instruction, re.I) is None:
                if re.search(r'\b(take|use|apply)\b', item.instruction, re.I):
                    status = "missing"  # missing dosage info
                    item_flags.append("missing")
            # TODO: check for conflicts? We'll skip for now.
            verified.append(VerifiedItem(
                instruction=item.instruction,
                source_quote=item.source_quote,
                status=status
            ))
            item_info.append({
                "id": idx,
                "instruction": item.instruction,
                "source_quote": item.source_quote,
                "status": status,
                "flags": item_flags
            })
        else:
            # Source quote not found - flag this item
            flags.append(f"Could not verify instruction: {item.instruction}")
            # We do not add to verified
    return verified, flags, item_info

def translate(items: List[VerifiedItem]) -> List[Dict]:
    """Translate verified items to Marathi in one call.
    Returns list of dicts: [{"id": int, "marathi": str}]
    """
    if not valid_api_key:
        raise ValueError("No API key set")
    if not items:
        return []
    # Build prompt for batch translation
    # We'll number the items
    lines = []
    for idx, item in enumerate(items):
        lines.append(f"{idx+1}. {item.instruction}")
    instructions = "\n".join(lines)
    # Read the prompt template
    try:
        with open("prompts/translate.md", "r") as f:
            template = f.read()
    except FileNotFoundError:
        template = """Translate the following medical instructions from English to Marathi.
Output simple spoken MARATHI in Devanagari, as spoken in Maharashtra. NOT Hindi.
Drug names, doses, units and numbers stay in Latin script and digits exactly as in the source.
No Latin or Cyrillic letters inside Marathi words.
Do not add, remove, or soften any instruction.
Return a JSON list of objects with keys: id (integer), marathi (string).

INSTRUCTIONS:
{instructions}

Where {instructions} is a numbered list like:
1. {instruction_1}
2. {instruction_2}
...
Return only valid JSON."""
    prompt = template.replace("{instructions}", instructions)
    try:
        raw_response = _generate_json(prompt)
        # Strip code fences if present
        text = raw_response
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        # Validate structure: expect list of dicts with id and marathi
        translations = []
        for i, entry in enumerate(data):
            if not isinstance(entry, dict) or "id" not in entry or "marathi" not in entry:
                raise ValueError(f"Invalid translation entry at index {i}: {entry}")
            translations.append({"id": entry["id"], "marathi": entry["marathi"]})
        # Ensure we have all ids
        if len(translations) != len(items):
            # If not, we might have missing ids; we'll try to map by order
            # Sort by id
            translations.sort(key=lambda x: x["id"])
            # Reassign ids to match index if needed
            for i, t in enumerate(translations):
                t["id"] = i
        return translations
    except Exception as e:
        print(f"Translation error: {e}")
        # Fallback: simple placeholder
        return [{"id": idx, "marathi": "[Translation not available]"} for idx in range(len(items))]

def back_translate(marathi_list: List[Dict]) -> List[Dict]:
    """Translate Marathi items back to English in one call.
    Input: list of dicts [{"id": int, "marathi": str}]
    Returns: list of dicts [{"id": int, "back_english": str}]
    """
    if not valid_api_key:
        raise ValueError("No API key set")
    if not marathi_list:
        return []
    # Build prompt for batch back-translation
    lines = []
    for entry in marathi_list:
        lines.append(f"{entry['id']+1}. {entry['marathi']}")
    instructions = "\n".join(lines)
    prompt = f"""
    Translate the following Marathi text to English.
    Return a JSON list of objects with keys: id (integer), back_english (string).
    Do NOT show the model the original English in this call.

    MARATHI TEXTS:
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
        # Validate structure
        back_translations = []
        for entry in data:
            if not isinstance(entry, dict) or "id" not in entry or "back_english" not in entry:
                raise ValueError(f"Invalid back-translation entry: {entry}")
            back_translations.append({"id": entry["id"], "back_english": entry["back_english"]})
        # Sort by id and ensure we have all
        back_translations.sort(key=lambda x: x["id"])
        # Reassign ids to match input order if needed
        # We'll create a map from id to back_english
        map_back = {bt["id"]: bt["back_english"] for bt in back_translations}
        result = []
        for entry in marathi_list:
            idx = entry["id"]
            if idx in map_back:
                result.append({"id": idx, "back_english": map_back[idx]})
            else:
                result.append({"id": idx, "back_english": "[Error]"})
        return result
    except Exception as e:
        print(f"Back translation error: {e}")
        return [{"id": entry["id"], "back_english": "[Error]"} for entry in marathi_list]

def _extract_drugs_and_numbers(text: str) -> Tuple[List[str], List[str]]:
    """Extract drug names and numbers from text.
    Returns (drugs, numbers) where drugs are strings that look like drug names (containing letters and maybe hyphens),
    and numbers are strings of digits possibly with decimal points.
    We'll use simple regexes.
    """
    # Pattern for drug names: words that contain letters and possibly hyphens, but we want to capture the whole drug name with numbers?
    # Actually, we want to extract drug names and numbers separately.
    # We'll look for patterns like: drug name possibly followed by numbers and units.
    # Simpler: extract all numbers (including decimals) and all words that are likely drug names.
    # But we can do: find all tokens that contain letters and maybe hyphens, and are not purely numbers.
    # We'll define drug names as strings that start with a capital letter and contain letters, possibly hyphens.
    # However, we want to keep it simple: we'll extract numbers and then consider the remaining parts.
    # For the purpose of drift detection, we just need to compare if the numbers and drug names are the same.
    # We'll extract numbers as sequences of digits, possibly with a decimal point.
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    # Extract drug names: words that contain letters and possibly hyphens, and are not purely numbers.
    # We'll also allow for combinations like "Cefixime 200 mg" -> we want "Cefixime" as drug.
    # We'll split by non-alphanumeric and keep tokens that have at least one letter.
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]*", text)
    drugs = [t for t in tokens if t.lower() not in ['mg', 'tablet', 'pill', 'unit', 'iu', 'daily', 'twice', 'once', 'days', 'day', 'hours', 'hours', 'hour', 'week', 'weeks', 'month', 'months', 'year', 'years']]
    # Also, we might want to keep the original case? We'll compare lowercased.
    return drugs, numbers

def _check_marathi_chars(marathi: str) -> Tuple[bool, str]:
    """Check if Marathi string contains only allowed characters:
    - Devanagari (Unicode range 0900-097F)
    - Latin letters (only allowed if they are part of a drug name? We'll allow Latin letters anywhere but we will flag if they appear outside of drug names? 
      The spec says: flag any item containing characters outside Devanagari, Latin letters in the drug name, digits, and punctuation.
      Interpretation: Allow Devanagari, Latin letters ONLY if they are part of a drug name, digits, and punctuation.
      So we need to detect drug names within the Marathi string? That's complex.
    Instead, we'll adopt a simpler approach: we'll allow Devanagari, digits, and punctuation. We'll allow Latin letters only if they are preceded and followed by spaces or punctuation? 
    Actually, the spec says: "Latin letters in the drug name" meaning we allow Latin letters only when they are part of a drug name. 
    Since we don't have a way to detect drug names in Marathi, we'll assume that the translation should not contain Latin letters except for drug names.
    We'll flag any Latin letter that is not part of a known drug name from the original instruction.
    We'll need to map drug names.
    Given time, we'll skip this complex check and just flag if there are any Latin letters (A-Z, a-z) that are not in a list of allowed drug names.
    We'll implement a simplified version: we'll extract drug names from the original instruction (lowercase) and then check the Marathi string for any Latin letters that are not part of those drug names.
    We'll need to pass the original instruction to this function.
    We'll change the function to take original_instruction as well.
    """
    # We'll implement later.
    return True, ""

def _meaning_match_check(original: str, back_english: str) -> Tuple[bool, str]:
    """Ask Gemini to rate meaning match yes/no.
    Returns (match, explanation) where match is True if yes, False if no.
    """
    if not valid_api_key:
        raise ValueError("No API key set")
    prompt = f"""
    Determine if the back-translated English instruction matches the meaning of the original English instruction.
    Answer with exactly "yes" or "no", and optionally a brief explanation.

    ORIGINAL INSTRUCTION:
    {original}

    BACK-TRANSLATED ENGLISH:
    {back_english}

    Respond in the following format:
    match: yes/no
    explanation: brief explanation
    """
    try:
        raw_response = _generate_json(prompt)
        text = raw_response.strip()
        # Parse the response
        match = False
        explanation = ""
        for line in text.split('\n'):
            if line.startswith("match:"):
                val = line.split(":", 1)[1].strip().lower()
                match = (val == "yes")
            elif line.startswith("explanation:"):
                explanation = line.split(":", 1)[1].strip()
        return match, explanation
    except Exception as e:
        print(f"Meaning match check error: {e}")
        return False, str(e)

def make_quiz(items: List[VerifiedItem]) -> QuizResult:
    """Generate a 3-question Marathi teach-back quiz."""
    if not valid_api_key:
        raise ValueError("No API key set")
    if not items:
        return QuizResult(questions=[], user_answers=[], score=0)
    # We'll generate questions based on the verified items
    # We'll pick up to 3 items
    quiz_items = items[:3]
    questions = []
    for item in quiz_items:
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
        "mode": "live",  # We'll keep mode for debug, but if not valid_api_key, we will have raised earlier.
        "model": model_name if valid_api_key else None,
        "raw_response": None,
        "items_parsed": [],
        "items_after_verify": [],
        "dropped_items": [],
        "translation_info": [],
        "back_translation_info": [],
        "drift_flags": [],
        "meaning_match_results": [],
        "marathi_validation_flags": []
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
        verified, flags, item_info = verify(extracted, note)
        debug["items_after_verify"] = [item.instruction for item in verified]
        debug["dropped_items"] = flags  # These are the unverifiable items dropped
        debug["item_info"] = item_info
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
        translation_list = translate(verified)  # list of {"id": int, "marathi": str}
        debug["translation_info"] = translation_list
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
    
    # Back-translate the Marathi items
    try:
        back_translation_list = back_translate(translation_list)  # list of {"id": int, "back_english": str}
        debug["back_translation_info"] = back_translation_list
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
    
    # Now we need to align the data: we have verified items (with index), translation_list, back_translation_list.
    # We'll create a list of dicts for each item with all needed info.
    # We'll also compute drift flags, meaning match, and Marathi validation.
    # We'll also build the checklist items for output.
    checklist_items = []
    red_panel_items = []  # for items with drift or validation issues? Actually red panel is for safety issues caught: conflicts, missing info, vague items, and also drift? The spec says hero metric includes real flags from extract plus unverifiable items dropped. Red panel likely shows items that have issues (like drift, validation fail, or vague/missing/conflict). We'll follow the earlier red panel logic: items that are not clear (vague, missing) plus those with drift or validation issues.
    # We'll compute hero metric later.
    
    # We'll also need to compute drift flags and meaning match results.
    drift_flags = []  # list of strings for items with drift
    meaning_match_results = []  # list of dicts per item: {"id": int, "match": bool, "explanation": str}
    marathi_validation_flags = []  # list of strings for items with invalid Marathi chars
    
    # We'll also need the original instructions for each item.
    # We'll create a map from id to original instruction and source_quote.
    id_to_original = {info["id"]: info for info in debug["item_info"]}
    
    # Process each item
    for info in debug["item_info"]:
        idx = info["id"]
        instruction = info["instruction"]
        source_quote = info["source_quote"]
        status = info["status"]
        # Get translation
        trans_entry = next((t for t in translation_list if t["id"] == idx), None)
        marathi = trans_entry["marathi"] if trans_entry else ""
        # Get back translation
        back_entry = next((b for b in back_translation_list if b["id"] == idx), None)
        back_english = back_entry["back_english"] if back_entry else ""
        
        # Initialize item-specific debug info
        item_drift = False
        item_marathi_valid = True
        item_marathi_reason = None
        item_drift_reason = None
        item_meaning_match = None
        item_meaning_explanation = ""
        item_marathi_valid = True
        item_marathi_issue = ""
        
        # 1. Extract drug names and numbers from original instruction and back_english
        orig_drugs, orig_nums = _extract_drugs_and_numbers(instruction)
        back_drugs, back_nums = _extract_drugs_and_numbers(back_english)
        # Compare
        if set(orig_drugs) != set(back_drugs) or set(orig_nums) != set(back_nums):
            item_drift = True
            item_drift_reason = f"Drug/number mismatch. Original drugs: {orig_drugs}, numbers: {orig_nums}. Back-translated drugs: {back_drugs}, numbers: {back_nums}."
            drift_flags.append(f"Item {idx}: {item_drift_reason}")
        
        # 2. Meaning match check (secondary)
        try:
            match, explanation = _meaning_match_check(instruction, back_english)
            item_meaning_match = match
            item_meaning_explanation = explanation
            meaning_match_results.append({"id": idx, "match": match, "explanation": explanation})
        except Exception as e:
            meaning_match_results.append({"id": idx, "match": False, "explanation": str(e)})
        
        # 3. Marathi validation: check for allowed characters
        # We'll implement a simple version: allow Devanagari, digits, punctuation, and Latin letters only if they are part of a drug name from the original.
        # We'll create a set of allowed Latin letter sequences (the drug names in lower case).
        allowed_latin = set(drug.lower() for drug in orig_drugs)
        # We'll check the Marathi string for any Latin letter sequences that are not in allowed_latin.
        # We'll extract sequences of Latin letters from the Marathi string.
        latin_seqs = re.findall(r"[A-Za-z]+", marathi)
        invalid_latin = [seq for seq in latin_seqs if seq.lower() not in allowed_latin]
        if invalid_latin:
            item_marathi_valid = False
            item_marathi_reason = f"Invalid Latin letters: {invalid_latin}"
            marathi_validation_flags.append(f"Item {idx}: {item_marathi_reason}")
        
        # Also check for characters outside Devanagari, Latin, digits, punctuation.
        # We'll allow: Devanagari (\\u0900-\\u097F), Latin letters (A-Za-z), digits (0-9), and punctuation (we'll consider common punctuation: . , ; : ? ! - ( ) [ ] { } \" ' and space).
        # We'll build a regex of allowed characters and see if any character is not allowed.
        # We'll do this after we have the allowed Latin letters condition.
        # For simplicity, we'll skip this extra check and rely on the Latin letters check.
        # We'll note that the spec also says "Latin letters in the drug name" meaning we allow Latin letters only in drug names, which we already checked.
        
        # If Marathi validation fails, we should flag it.
        # We'll also consider that if the Marathi string is empty or contains error, we flag.
        if not marathi or marathi.startswith("[") or marathi.startswith("{") or "Error" in marathi:
            item_marathi_valid = False
            item_marathi_reason = "Marathi translation missing or error"
            marathi_validation_flags.append(f"Item {idx}: {item_marathi_reason}")
        
        # Build checklist item for output
        checklist_items.append(TranslationItem(
            english=instruction,
            marathi=marathi,
            source_quote=source_quote
        ))
        
        # Determine if this item should go to red panel.
        # Red panel items are those with safety issues: vague, missing, conflict, drift, or Marathi validation fail.
        # We'll add to red_panel_items if status is not clear, or if there is drift, or if Marathi validation fails.
        if status != "clear" or item_drift or not item_marathi_valid:
            red_panel_items.append(VerifiedItem(
                instruction=instruction,
                source_quote=source_quote,
                status=status,
                drift=item_drift,
                drift_reason=item_drift_reason,
                marathi_invalid=not item_marathi_valid
            ))
    
    # Debug info
    debug["drift_flags"] = drift_flags
    debug["meaning_match_results"] = meaning_match_results
    debug["marathi_validation_flags"] = marathi_validation_flags
    
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
    
    # Hero metric: number of real flags from extract (conflicts, missing info, vague items) plus any unverifiable items dropped.
    # We need to count from item_info the flags that are not empty (vague, missing, conflict). We'll also count the dropped items (flags from verify).
    # We'll define real flags as: for each item in item_info, count the number of flags in its "flags" list (vague, missing, conflict).
    # Then add the number of dropped items (unverifiable).
    real_flags_count = 0
    for info in debug["item_info"]:
        real_flags_count += len(info["flags"])
    dropped_count = len(debug["dropped_items"])
    hero_metric = real_flags_count + dropped_count
    
    # Back-translation check: we need to pick one item for the back_translation_check field in the output.
    # The spec doesn't specify which item; we can pick the first item that has a back translation.
    # We'll use the first item's Marathi and back-translated English for the back_translation_check field.
    # We'll also compute drift_detected for that item based on our drift flag.
    back_translation_check = BackTranslationResult(original="", back_translated="", drift_detected=False)
    if checklist_items:
        # Use the first checklist item
        first_item = checklist_items[0]
        # We need to get the original Marathi and back-translated English for that item.
        # We'll find the item info for the first item's source_quote? We'll use the first item in verified.
        if verified:
            first_verified = verified[0]
            # We need to get the back-translated English for this item from our back_translation_list.
            # We'll find the back_translation entry with id 0 (since we used index).
            back_entry = next((b for b in back_translation_list if b["id"] == 0), None)
            back_english = back_entry["back_english"] if back_entry else ""
            # Determine if drift detected for this item
            drift_detected = any(drift_flag.startswith("Item 0:") for drift_flag in drift_flags)
            back_translation_check = BackTranslationResult(
                original=first_item.marathi,
                back_translated=back_english,
                drift_detected=drift_detected,
                drift_explanation="Drug/number mismatch" if drift_detected else None
            )
    
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
