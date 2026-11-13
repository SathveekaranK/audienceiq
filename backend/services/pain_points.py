"""Pain point detection shared by the analysis and read endpoints.

Pain points are surfaced by scanning comment text for complaint phrases
rather than by relying on sentiment alone. Many real complaints are mixed
sentiment ("Great video, but the explanation was too fast"), so VADER
classifies them as positive and a sentiment-only filter would miss them.

Sentiment is still used, but as a *weight* rather than a filter:
    negative  -> counted fully
    neutral   -> counted fully
    positive  -> counted only when the comment shows a clear complaint
                 pattern (an explicit contrast marker such as "but",
                 "however", "wish", "could", "too", "missing")
"""

from typing import Dict, List, Optional

# Complaint categories and the phrases that signal them.
PAIN_KEYWORDS: Dict[str, List[str]] = {
    "too_fast": [
        "fast", "speed", "quick", "rush", "hurry", "too quickly", "too fast",
        "faster", "rewind", "skip ahead",
    ],
    "too_theory": [
        "theory", "theoretical", "abstract", "hard to understand",
        "confusing", "complicated", "too much theory",
    ],
    "not_practical": [
        "practical", "demo", "demonstration", "example", "hands-on",
        "hands on", "project", "walkthrough", "show me",
    ],
    "assumes_knowledge": [
        "prior knowledge", "assume", "previous", "experience",
        "beginner", "beginners", "newbie", "never heard",
    ],
    "missing_resources": [
        "resource", "link", "reference", "material", "documentation",
        "download", "slides", "code sample", "source code",
    ],
    "too_long": [
        "too long", "length", "duration", "boring", "rambl", "verbose",
        "skip ahead",
    ],
}

# Words that mark a complaint inside an otherwise positive comment.
_CONTRAST_MARKERS = (
    "but ", "however", "wish ", "could ", "should ", "too ", "missing",
    "lack", "needs", "would be", "please make", "please include",
    "didn't ", "doesn't ", "not enough", "more ",
)


def _has_contrast_marker(text: str) -> bool:
    return any(marker in text for marker in _CONTRAST_MARKERS)


def detect_pain_points(
    comments: List[dict],
) -> List[dict]:
    """Find recurring complaints across comments.

    Each comment is a dict with:
        comment_id, text, processed (optional), sentiment (optional)

    Returns a list of dicts sorted by how often each category appears.
    """
    hits: Dict[str, List[dict]] = {key: [] for key in PAIN_KEYWORDS}

    for comment in comments:
        raw = comment.get("text") or ""
        text = (comment.get("processed") or raw).lower()
        if not text.strip():
            continue

        sentiment = comment.get("sentiment") or "unanalyzed"

        for pain_key, keywords in PAIN_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in text]
            if not matched:
                continue

            # A positive comment only counts when it clearly expresses a
            # complaint; otherwise "great video, great examples" would be
            # reported as a pain point.
            if sentiment == "positive" and not _has_contrast_marker(text):
                continue

            hits[pain_key].append({
                "comment_id": comment.get("comment_id"),
                "text": raw,
                "sentiment": sentiment,
                "matched": matched,
            })

    total = sum(len(v) for v in hits.values()) or 1

    pain_points = []
    for key, examples in hits.items():
        if not examples:
            continue
        pain_points.append({
            "type": key,
            "label": key.replace("_", " ").title(),
            "count": len(examples),
            "share": round((len(examples) / total) * 100, 2),
            "examples": examples[:3],
        })

    pain_points.sort(key=lambda p: p["count"], reverse=True)
    return pain_points
