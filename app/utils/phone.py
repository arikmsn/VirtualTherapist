"""Phone number normalization utilities."""

import re


def normalize_phone(phone: str) -> str:
    """
    Normalize a phone number to E.164 format.

    Strips formatting characters (spaces, dashes, parentheses, dots).
    Converts 00-prefix to + prefix.
    Auto-adds +972 prefix for Israeli local numbers starting with 0.

    Returns the E.164 string, e.g. "+972501234567".
    Raises ValueError if the result is not a valid E.164 number.
    """
    if not phone or not phone.strip():
        raise ValueError("Phone number cannot be empty")

    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone.strip())

    # International dialing prefix 00... → +
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]

    # Israeli local format 05X... → +97205X... (strip leading 0, prepend +972)
    if cleaned.startswith('0') and not cleaned.startswith('0+'):
        cleaned = '+972' + cleaned[1:]

    # Validate E.164: starts with + followed by 7–15 digits
    if not cleaned.startswith('+'):
        raise ValueError(
            f"Cannot normalize phone number '{phone}'. "
            "Expected E.164 (+XXXXXXXXXXX) or Israeli local format (05X...)."
        )

    digits = cleaned[1:]
    if not digits.isdigit():
        raise ValueError(
            f"Phone number '{phone}' contains non-digit characters after country code."
        )

    if not (7 <= len(digits) <= 15):
        raise ValueError(
            f"Phone number '{phone}' has invalid length "
            f"({len(digits)} digits after '+'). Expected 7–15 digits."
        )

    return cleaned
