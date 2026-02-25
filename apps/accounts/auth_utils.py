import re

def normalize_mobile(mobile: str) -> str:
    if not mobile:
        return ""
    return re.sub(r"\D+", "", str(mobile))