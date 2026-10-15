
import re
from collections import Counter
from pathlib import Path


TYPE_HINTS = {
    "Mortgage": ["mortgage", "mortgagor", "mortgagee"],
    "Power of Attorney": ["power of attorney"],
    "Affidavit": ["affidavit"],
    "Lease": ["lease", "lessor", "lessee"],
    "Legal Notice": ["legal notice", "notice"],
    "Court Order": ["court order", "order of the court", "in the high court", "judgment"],
    "Invoice": ["invoice"],
    "Deed": ["deed"],
    "Contract": ["contract", "agreement"],
    "Letter": ["dear sir", "dear madam", "yours faithfully", "yours sincerely"],
}

COMPANY_SUFFIX = r"(?i:pvt\.?[ \t]+ltd\.?|private[ \t]+limited|limited|ltd\.?|llp|llc|inc\.?|corporation|corp\.?|company|bank)"
COMPANY_PATTERN = re.compile(rf"\b((?:[A-Z][\w&.'-]*[ \t]+){{0,5}}{COMPANY_SUFFIX})(?![\w])")


def guess_company(text, known=()):
    lowered = text.lower()
    found = [(lowered.find(name.lower()), name) for name in known if name.lower() in lowered]
    if found:
        return min(found)[1]

    candidates = []
    for match in COMPANY_PATTERN.finditer(text):
        name = " ".join(match.group(1).split()).rstrip(".")
        name = re.sub(r"^(The|This|That|And|Of|To|By)\s+", "", name)
        if len(name.split()) > 1:  # "Bank" or "Limited" on its own is not a name
            candidates.append(name)
    if not candidates:
        return ""
    counts = Counter(candidates)
    best = max(counts.values())
    return next(name for name in candidates if counts[name] == best)  # most often, earliest on a tie


def guess_type(text, known=()):
    """The document type the first page talks about most, with the title area counting extra."""
    hints = {name: list(words) for name, words in TYPE_HINTS.items()}
    for name in known:
        if name.lower() not in (n.lower() for n in hints):
            hints[name] = [name.lower()]

    body = text[:1500].lower()
    title_area = text[:200].lower()
    scores = {}
    for name, words in hints.items():
        scores[name] = sum(body.count(w) + 3 * title_area.count(w) for w in words)

    best = max(scores.values(), default=0)
    if best == 0:
        return ""
    name = next(n for n, score in scores.items() if score == best)
    # use the spelling already in the database if there is one
    return next((k for k in known if k.lower() == name.lower()), name)


def guess_details(text, filename="", companies=(), types=()):
    return {
        "title": Path(filename).stem,
        "company": guess_company(text, companies),
        "document_type": guess_type(text, types),
    }
