"""Resolve supported English day references without asking a model to guess."""
import re
from datetime import date, timedelta

DAY = re.compile(r"\b(today|yesterday|tomorrow)\b", re.IGNORECASE)
OTHER_RELATIVE = re.compile(
    r"\b(?:last|this|next|past|previous|current)\s+(?:(?:\d+|few|several)\s+)?"
    r"(?:hours?|days?|weeks?|months?|years?|weekends?|nights?)\b"
    r"|\b(?:\d+\s+(?:hours?|days?|weeks?|months?|years?)\s+ago|recently|tonight|now)\b",
    re.IGNORECASE,
)


class ClarificationRequired(ValueError):
    pass


def resolve_question(question, reference_date=None):
    anchor = None
    if reference_date is not None:
        try:
            anchor = date.fromisoformat(reference_date)
            if anchor.isoformat() != reference_date:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Reference date must be a valid YYYY-MM-DD date.") from None
    if OTHER_RELATIVE.search(question):
        raise ClarificationRequired("Please replace the relative time period with explicit UTC start and end dates. Only today, yesterday, and tomorrow can be resolved automatically.")
    if DAY.search(question) and anchor is None:
        raise ClarificationRequired("Please supply --reference-date YYYY-MM-DD (UTC), or replace the relative day with an explicit date.")

    def replace(match):
        offset = {"today": 0, "yesterday": -1, "tomorrow": 1}[match.group().lower()]
        try:
            resolved = anchor + timedelta(days=offset)
        except OverflowError:
            raise ValueError("Resolved date is outside the supported calendar range.") from None
        return f"on {resolved.isoformat()} UTC"

    return DAY.sub(replace, question)
