# SPEC

**User**: Hospital staff and patients' families in India needing to understand discharge notes.

**Outputs**:
1. Marathi checklist with traceable source quotes.
2. Red panel for missing, conflicting, or vague instructions.
3. Back-translation check for meaning drift.
4. Marathi teach-back quiz to identify misunderstandings.
5. Hero metric: "N safety issues caught before discharge."

**Non-Goals**:
- Not a diagnostic tool.
- Not a replacement for clinician judgment.
- Not for real patient data (synthetic only).
- Not for non-English discharge notes (other than English input and Marathi output).

**Success Criteria**:
- Catch at least 80% of planted safety issues in synthetic tests.
- Refuse generation when note is too incomplete or contradictory.
- All Marathi output must be traceable to source quotes.
