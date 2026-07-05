import re

def detect_prompt_injection(text: str) -> bool:
    """
    Scans the input text for common prompt injection attempts.
    Returns True if an injection is detected, False otherwise.
    """
    if not text:
        return False
        
    text = text.lower()
    
    # Common prompt injection patterns
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
        r"developer mode"
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text):
            return True
            
    # Heuristic: Extremely high number of special characters often indicates an obfuscation attack
    special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', text)) / (len(text) + 1)
    if special_char_ratio > 0.4 and len(text) > 20:
        return True
        
    return False
