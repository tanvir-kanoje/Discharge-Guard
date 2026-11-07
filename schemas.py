from pydantic import BaseModel
from typing import List, Optional, Literal

class ExtractedItem(BaseModel):
    instruction: str
    source_quote: str

class VerifiedItem(BaseModel):
    instruction: str
    source_quote: str
    status: Literal["clear", "missing", "conflicting", "vague"]
    drift: bool = False
    drift_reason: Optional[str] = None
    marathi_invalid: bool = False

class TranslationItem(BaseModel):
    english: str
    marathi: str
    source_quote: str

class BackTranslationResult(BaseModel):
    original: str
    back_translated: str
    drift_detected: bool
    drift_explanation: Optional[str] = None

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    source_quote: str

class QuizResult(BaseModel):
    questions: List[QuizQuestion]
    user_answers: List[str]
    score: int

class PipelineOutput(BaseModel):
    checklist: List[TranslationItem]
    red_panel_items: List[VerifiedItem]
    back_translation_check: BackTranslationResult
    teach_back_quiz: QuizResult
    hero_metric: int
    refusal_reason: Optional[str] = None
    can_generate: bool = True
