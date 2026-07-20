"""Prompt injection detection — scans user input for known attack patterns before trial entry."""
import re
import unicodedata
from typing import Optional

_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"

_LEGAL_PUNCTUATION = set("§()&,.'\"-;:!?/¶©")


def detect_prompt_injection(text: Optional[str]) -> bool:
    """
    Scans the input text for common prompt injection attempts.
    Returns True if an injection is detected, False otherwise.
    """
    if not text:
        return False

    text = unicodedata.normalize("NFKD", text)
    for ch in _ZERO_WIDTH_CHARS:
        text = text.replace(ch, "")
    text = text.lower()

    suspicious_patterns = [
        r"ignore (?:all )?previous instructions",
        r"disregard (?:all )?previous instructions",
        r"you are now (a|an|the)",
        r"forget everything",
        r"system prompt",
        r"new rule",
        r"override (?:safety|content|filter|restrictions|guidelines|protocols)",
        r"bypass (?:safety|content|filter|restrictions|guidelines|protocols)",
        r"jailbreak",
        r"print (?:your )?instructions",
        r"developer mode",
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, text):
            return True

    special_chars = re.findall(r"[^a-zA-Z0-9\s]", text)
    non_legal = [c for c in special_chars if c not in _LEGAL_PUNCTUATION]
    special_char_ratio = len(non_legal) / (len(text) + 1)
    if special_char_ratio > 0.4 and len(text) > 20:
        return True

    return False
