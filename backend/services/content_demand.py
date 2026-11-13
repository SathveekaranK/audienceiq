"""Content demand detection.

Finds the comments where a viewer is effectively asking for more content -
"can you explain X", "please make a part 2", "how do I do X" - so a creator
can see what to make next.
"""

from typing import Any, Dict, List, Optional

# Request patterns keyed by the category stored in the database.
REQUEST_PATTERNS: Dict[str, List[str]] = {
    "tutorial_request": [
        "tutorial", "please make", "how to", "guide", "walkthrough",
        "step by step", "step-by-step", "how do i",
    ],
    "comparison_request": [
        "compare", "vs", "versus", "difference between", "better than",
        "which is better",
    ],
    "explanation_request": [
        "explain", "clarify", "understand", "why", "how does", "what is",
        "can you explain", "don't understand", "dont understand",
    ],
    "updated_content_request": [
        "updated", "new version", "latest", "current", "recent", "still valid",
    ],
    "project_walkthrough": [
        "project", "walkthrough", "build", "create", "example", "full code",
        "source code", "demo",
    ],
}

# Words that hint at what the viewer wants the video to be about.
_TOPIC_HINTS = [
    "ai", "python", "machine", "learning", "tutorial", "code", "javascript",
    "react", "docker", "kubernetes", "sql", "excel", "figma", "prompt",
    "automation", "api", "css", "html", "java", "rust", "go",
]


class ContentDemandDetector:
    """Detect explicit requests for more content."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence

    def detect_requests(self, texts: List[str]) -> Dict[str, Any]:
        """Return the requests found in a list of comment texts.

        The result has:
            requests        - list of {category, topic, confidence, comment}
            by_category     - {category: count}
        """
        requests: List[Dict[str, Any]] = []

        for text in texts:
            if not text:
                continue
            lowered = text.lower()

            category: Optional[str] = None
            confidence = 0.0

            for request_type, patterns in REQUEST_PATTERNS.items():
                for pattern in patterns:
                    if pattern in lowered:
                        category = request_type
                        confidence = min(0.5 + (lowered.count(pattern) * 0.1), 1.0)
                        break
                if category:
                    break

            if not category or confidence < self.min_confidence:
                continue

            topic = self._extract_topic(lowered)

            requests.append({
                "category": category,
                "topic": topic or "general content",
                "confidence": round(confidence, 2),
                "comment": text[:160],
            })

        by_category: Dict[str, int] = {}
        for request in requests:
            by_category[request["category"]] = by_category.get(request["category"], 0) + 1

        return {
            "requests": requests,
            "by_category": by_category,
            "total": len(requests),
        }

    @staticmethod
    def _extract_topic(lowered: str) -> Optional[str]:
        """Pull a rough topic word out of the comment."""
        words = lowered.replace(",", " ").replace(".", " ").split()
        for word in words:
            if word in _TOPIC_HINTS:
                return word
        return None
