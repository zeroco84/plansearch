"""Text normalisation utilities for PlanSearch."""

import re
import unicodedata


def clean_text(text: str | None) -> str | None:
    """Clean and normalise text from CSV data.

    - Strips leading/trailing whitespace
    - Collapses multiple spaces
    - Removes control characters
    - Normalises unicode
    """
    if not text or not text.strip():
        return None

    # Normalise unicode
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text if text else None


def normalise_reg_ref(reg_ref: str) -> str:
    """Normalise a planning registration reference.

    Handles formats like:
    - 2024/12345
    - FRL/2024/12345
    - WEB/2024/12345
    """
    return reg_ref.strip().upper()


def normalise_decision(decision: str | None) -> str | None:
    """Normalise decision status to consistent values."""
    if not decision:
        return None

    decision = decision.strip().upper()

    # Map common variations
    mapping = {
        "GRANT PERMISSION": "GRANTED",
        "GRANT": "GRANTED",
        "GRANTED": "GRANTED",
        "CONDITIONAL": "GRANTED",
        "REFUSE PERMISSION": "REFUSED",
        "REFUSE": "REFUSED",
        "REFUSED": "REFUSED",
        "SPLIT DECISION": "SPLIT",
        "SPLIT": "SPLIT",
        "FURTHER INFORMATION": "FURTHER_INFO",
        "REQUEST ADDITIONAL INFORMATION": "FURTHER_INFO",
        "ADDITIONAL INFORMATION": "FURTHER_INFO",
        "WITHDRAWN": "WITHDRAWN",
        "INVALID": "INVALID",
    }

    return mapping.get(decision, decision)


def normalise_address(address: str | None) -> str | None:
    """Normalise an address string.

    - Title-cases
    - Normalises common abbreviations
    - Removes double commas
    """
    if not address:
        return None

    # Clean first
    address = clean_text(address)
    if not address:
        return None

    # Title case
    address = address.title()

    # Fix common Dublin abbreviations
    address = re.sub(r"\bSt\b", "Street", address)
    address = re.sub(r"\bRd\b", "Road", address)
    address = re.sub(r"\bAve\b", "Avenue", address)

    # Clean up commas
    address = re.sub(r",\s*,", ",", address)

    return address.strip()
