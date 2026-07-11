"""
Tests for logical section parsing performed during standardization.

Behaviors covered:
- Section names are normalized consistently.
- Parenthetical section descriptions are preserved separately.
- Section text is extracted without surrounding artifacts.
- Section-level issuance lines are removed from text.
- Removed issuance lines are retained as section metadata.
- Valid section timestamps are normalized to UTC.
- Invalid section timestamps do not discard the section.
- Section terminators such as && and $$ are handled.
- Preferred sections are combined into model input text.
- Raw text is used when preferred sections are unavailable.
"""