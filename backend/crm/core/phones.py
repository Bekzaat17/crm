import re


def phone_digits(value):
    """Цифры номера для сравнения: 8XXXXXXXXXX → 7XXXXXXXXXX (Казахстан)."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits[:20]
