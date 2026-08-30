import re

GSM_7_CHARS = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_7_EXT_CHARS = {"^", "~", "\\", "[", "]", "|", "{", "}", "\n"}

GSM_7_MAX_SINGLE = 160
GSM_7_MAX_MULTI = 153
UCS_2_MAX_SINGLE = 70
UCS_2_MAX_MULTI = 67


def detect_encoding(text: str) -> str:
    for ch in text:
        if ch not in GSM_7_CHARS and ch not in GSM_7_EXT_CHARS:
            return "ucs_2"
    return "gsm_7"


def estimate_sms_parts(text: str, encoding: str = "auto") -> tuple[int, int]:
    if encoding == "auto":
        encoding = detect_encoding(text)
    length = len(text)
    if encoding == "gsm_7":
        if length <= GSM_7_MAX_SINGLE:
            return 1, GSM_7_MAX_SINGLE
        parts = (length + GSM_7_MAX_MULTI - 1) // GSM_7_MAX_MULTI
        return parts, GSM_7_MAX_MULTI
    else:
        if length <= UCS_2_MAX_SINGLE:
            return 1, UCS_2_MAX_SINGLE
        parts = (length + UCS_2_MAX_MULTI - 1) // UCS_2_MAX_MULTI
        return parts, UCS_2_MAX_MULTI


def split_message(text: str, encoding: str = "auto") -> list[str]:
    if encoding == "auto":
        encoding = detect_encoding(text)
    max_per_part = GSM_7_MAX_MULTI if encoding == "gsm_7" else UCS_2_MAX_MULTI
    if len(text) <= max_per_part:
        return [text]
    parts = []
    for i in range(0, len(text), max_per_part):
        parts.append(text[i:i + max_per_part])
    return parts
