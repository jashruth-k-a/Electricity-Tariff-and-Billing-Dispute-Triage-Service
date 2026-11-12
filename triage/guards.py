import re


# Deliberately transparent baseline: evaluated attack patterns, not a claim of complete protection.
INJECTION = re.compile(
    r"ignore\s+(all\s+|the\s+|any\s+)?(previous|above|system|prior)\s+(instructions?|prompts?)"
    r"|\b(system|developer)\s*(message|prompt)\s*:|<\|(?:im_start|system)\|>"
    r"|reveal.{0,30}(secret|api.key|system.prompt)|\b(call|execute)\s+(shell|bash|powershell)"
    r"|\boverride\s+(the\s+)?(rules|instructions)|\bdisregard\s+(all\s+)?instructions", re.I | re.S)
TOXIC = re.compile(r"\b(?:idiot|moron|stupid|fuck(?:ing)?|shit|kill\s+yourself)\b", re.I)
AUTHORITY = re.compile(r"\b(?:bill\s+(?:has\s+been|is\s+hereby)\s+(?:revised|cancelled)|"
                       r"legally\s+binding|final\s+(?:legal\s+)?determination|"
                       r"you\s+must\s+pay|payment\s+is\s+ordered)\b", re.I)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def check_text(value, output=False):
    for text in strings(value):
        if INJECTION.search(text):
            return "prompt-injection-pattern"
        if TOXIC.search(text):
            return "toxicity-pattern"
        if output and AUTHORITY.search(text):
            return "unauthorised-determination"
    return None
