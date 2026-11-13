"""Emotion detection for YouTube comments.

Goes beyond a simple positive / negative split and answers the questions a
creator actually cares about:

* **influenced** - the video changed their mind or moved them to act
* **triggered**   - the video hit them emotionally
* **hate**        - they dislike the content or the creator
* **love**        - genuine appreciation
* **curious**     - they want more (this is content demand in disguise)
* **neutral**     - nothing in particular

Detection is multi-label: a comment can be *triggered* and *hate* at the same
time ("this is disgusting, I can't stop watching"). The strongest signal
becomes the comment's primary emotion, while every emotion that cleared the
threshold is kept so the dashboard can show overlaps.

The engine is a weighted lexicon with intensity modifiers, negation
handling and contrast markers. It is deliberately explainable - every hit
carries the phrase that triggered it - and it works offline, so analysis
never depends on a third party model.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Emotion lexicons
#
# Each entry is (phrase, weight). Multi-word phrases score higher because
# they are far less likely to be an accidental match.
# ---------------------------------------------------------------------------

LEXICONS: Dict[str, List[Tuple[str, float]]] = {
    "influenced": [
        # Explicit behaviour change
        ("changed my mind", 3.0), ("change my mind", 3.0),
        ("made me", 2.4), ("makes me", 2.2), ("made me want", 3.0),
        ("convinced me", 3.0), ("persuaded me", 3.0),
        ("inspired me", 3.0), ("motivated me", 3.0),
        ("opened my eyes", 3.2), ("eye opener", 3.0),
        ("after watching this", 2.6), ("after this video", 2.6),
        ("since watching", 2.4), ("after watching", 2.0),
        ("i subscribed", 2.6), ("subscribed after", 2.8),
        ("i started", 2.2), ("i'm going to", 2.2), ("i will", 1.6),
        ("i'm going", 1.8), ("i plan to", 2.4), ("planning to", 2.2),
        ("i decided", 2.2), ("i tried", 1.8), ("i'm trying", 2.0),
        ("i bought", 2.4), ("i ordered", 2.2), ("i booked", 2.4),
        ("i followed", 2.0), ("following this", 2.2),
        ("i learned", 2.0), ("i now", 1.6), ("now i", 1.6),
        ("gave me the", 2.0), ("this gave me", 2.4),
        ("you changed", 2.4), ("this changed", 2.6),
        ("will try", 2.0), ("going to try", 2.4),
        ("try pannunga", 2.4), ("try pannuvenum", 2.4),
        ("try panren", 2.2), ("vaanga venam", 2.0), ("vaangudhu", 1.8),
        ("pakren", 1.6), ("plan pannirukken", 2.4),
    ],
    "triggered": [
        # Strong emotional reaction
        ("wow", 1.6), ("omg", 1.8), ("oh my god", 2.4), ("omgg", 1.8),
        ("can't stop", 2.6), ("cannot stop", 2.6),
        ("stopped me", 1.8), ("so emotional", 2.8), ("emotional", 2.0),
        ("made me cry", 3.0), ("crying", 2.6), ("cried", 2.2),
        ("goosebumps", 3.0), ("mind blown", 3.0), ("blown away", 3.0),
        ("speechless", 2.8), ("shocking", 2.4), ("shocked", 2.2),
        ("insane", 2.0), ("crazy", 1.8), ("unreal", 2.0),
        ("so true", 2.4), ("literally", 1.4), ("no way", 2.0),
        ("what the", 1.6), ("heart", 1.6), ("my heart", 1.8),
        ("so happy", 2.2), ("so excited", 2.6), ("excited", 1.8),
        ("surprised", 2.0), ("amazed", 2.2), ("mind = blown", 3.0),
        ("escenic", 2.0), ("bayama", 1.8), ("pagal", 2.0),
    ],
    "hate": [
        # Dislike / contempt
        ("hate", 2.4), ("hated", 2.2), ("disgusting", 3.0),
        ("cringe", 2.8), ("cringey", 2.6), ("clickbait", 2.8),
        ("click bait", 2.8), ("worst", 2.8), ("the worst", 3.0),
        ("annoying", 2.2), ("irritating", 2.4), ("waste of time", 3.0),
        ("waste of money", 3.0), ("toxic", 2.6), ("trash", 2.4),
        ("pathetic", 2.8), ("awful", 2.4), ("terrible", 2.6),
        ("horrible", 2.4), ("gross", 2.2), ("boring", 2.0),
        ("scam", 3.0), ("misleading", 2.6), ("fake", 2.0),
        ("liar", 2.8), ("fraud", 2.8), ("garbage", 2.6),
        ("rubbish", 2.4), ("disgusted", 2.6), ("never again", 2.8),
        ("unfollowing", 2.8), ("not worth", 2.6), ("don't watch", 2.4),
        ("do not watch", 2.6), ("skip this", 2.0),
        ("vaiyadi", 2.4), ("venam", 1.8), ("kalichu", 2.2),
        ("theriyadhu", 2.0), ("kodu", 1.6), ("boring va", 2.2),
        ("yaarukku", 1.2),
    ],
    "love": [
        ("love", 2.2), ("loved", 2.2), ("love this", 2.8),
        ("amazing", 2.4), ("best", 2.0), ("excellent", 2.4),
        ("beautiful", 2.2), ("brilliant", 2.4), ("favorite", 2.2),
        ("favourite", 2.2), ("perfect", 2.2), ("great job", 2.6),
        ("so good", 2.2), ("superb", 2.4), ("wonderful", 2.4),
        ("helpful", 2.2), ("thank you", 1.8), ("thanks", 1.4),
        ("nice", 1.6), ("awesome", 2.2), ("fantastic", 2.4),
        ("good", 1.3), ("great", 1.6), ("nice one", 1.8),
        ("nalla", 2.2), ("super", 1.8), ("pandiya", 2.0),
        ("kalai", 2.0), ("mathangariga", 2.2), ("semma", 1.6),
        ("venum", 1.4), ("anna", 1.2),
    ],
    "curious": [
        # Demand for more
        ("please make", 2.6), ("please do", 2.4), ("make a part", 2.8),
        ("do a part", 2.8), ("please post", 2.4), ("please upload", 2.4),
        ("please", 1.2), ("can you", 1.4), ("could you", 1.4),
        ("how did you", 2.2), ("how do you", 2.2), ("how to", 1.8),
        ("explain", 2.0), ("tutorial", 1.8), ("any chance", 2.2),
        ("when is", 2.0), ("more videos", 2.6), ("next video", 2.4),
        ("part 2", 2.8), ("episode", 1.8), ("expecting", 1.8),
        ("waiting for", 2.2), ("looking forward", 2.4),
        ("where can i", 1.8), ("which one", 1.4), ("suggest", 1.4),
        ("velichu", 1.6), ("eppadi", 1.8), ("eppadi irukku", 2.0),
        ("venumna", 1.4), ("episodes", 1.8),
    ],
}

# Words that increase the intensity of whatever follows.
_INTENSIFIERS = {
    "very": 1.4, "really": 1.35, "so": 1.25, "super": 1.3, "extremely": 1.5,
    "incredibly": 1.5, "absolutely": 1.4, "totally": 1.3, "completely": 1.4,
    "highly": 1.3, "genuinely": 1.25, "seriously": 1.3, "honestly": 1.15,
    "slightly": 0.6, "somewhat": 0.7, "bit": 0.7, "kinda": 0.7,
    "maga": 1.4, "super ah": 1.3,
}

# Words that flip the meaning of what follows.
_NEGATIONS = {
    "not", "no", "never", "dont", "don't", "doesnt", "doesn't", "didnt",
    "didn't", "cannot", "cant", "can't", "wont", "won't", "isnt", "isn't",
    "arent", "aren't", "wasnt", "wasn't", "nobody", "nothing",
}

# Contrast markers - the complaint after "but" matters more than the praise
# before it.
_CONTRAST_MARKERS = ("but", "however", "though", "although", "yet")

# Emojis that reliably signal a strong reaction.
_EMOJI_TRIGGERED = set("😮😱🤯😳🥺😭😢😡🤬😤💔💯🔥👎🤮😩😫🥹")
_EMOJI_LOVE = set("❤️💕💖💗💓😍🥰😊😄😁🙌👏🤗✨🎉🥳👍")
_EMOJI_NEGATIVE = set("👎🤮😡😠🤬💩👎🏻👎🏼")

# Sentiment flip for negation: "not great" should not score as love.
_NEGATED_EMOTIONS = {"love", "hate", "triggered"}


class EmotionAnalyzer:
    """Score a comment against the emotion lexicons."""

    def __init__(self, min_score: float = 1.2, min_ratio: float = 0.30):
        self.min_score = min_score
        self.min_ratio = min_ratio

    # -- public -------------------------------------------------------------

    def analyze(self, text: str) -> Dict[str, object]:
        """Analyse one comment.

        Returns a dict with:
            primary       - the winning emotion label
            scores        - {emotion: score} for every emotion that matched
            labels        - every emotion that cleared the threshold
            confidence    - 0..1 how strongly the primary emotion matched
            signals       - the phrases that matched (for explainability)
            language      - detected script of the comment
            intensity     - 0..1 emotional intensity from emoji + caps
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return self._empty()

        lowered = self._normalise(cleaned)
        scores: Dict[str, float] = {}
        signals: Dict[str, List[str]] = {}

        for emotion, phrases in LEXICONS.items():
            total = 0.0
            hits: List[str] = []
            for phrase, weight in phrases:
                if phrase not in lowered:
                    continue
                score = weight * self._context_multiplier(lowered, phrase)
                if score == 0:
                    continue
                total += score
                hits.append(phrase)
            if total > 0:
                scores[emotion] = round(total, 3)
                signals[emotion] = hits
            elif total < 0:
                # A negated phrase ("not great") still tells us something:
                # the viewer is mildly unimpressed.
                scores[emotion] = round(total, 3)
                signals.setdefault(emotion, []).append(f"negated:{hits[0]}" if hits else "negated")

        # A negated positive ("not great", "not bad at all") is mild
        # disapproval, not enthusiasm. Route it to hate instead of dropping
        # the comment to neutral.
        for emotion, score in list(scores.items()):
            if emotion in _NEGATED_EMOTIONS and score < 0:
                scores.pop(emotion, None)
                scores["hate"] = round(scores.get("hate", 0.0) + abs(score) * 0.8, 3)
                signals.setdefault("hate", []).append(f"negated {emotion}")

        # Emoji and formatting intensity
        emoji_score, emoji_emotions = self._emoji_signals(cleaned)
        for emotion, amount in emoji_emotions.items():
            scores[emotion] = round(scores.get(emotion, 0.0) + amount, 3)

        # All caps is an intensity signal in English-heavy comments.
        caps = self._caps_intensity(cleaned)
        if caps > 0.5 and scores:
            loudest = max(scores, key=lambda k: scores[k])
            scores[loudest] = round(scores[loudest] * (1 + caps * 0.25), 3)

        if not scores:
            return self._empty(detected_language=self._detect_language(cleaned))

        # Only positive scores can win - a leftover negative score means the
        # phrase was negated, which is handled above.
        positive_scores = {k: v for k, v in scores.items() if v > 0}
        if not positive_scores:
            return self._empty(detected_language=self._detect_language(cleaned))

        top = max(positive_scores.values())
        labels = [
            emotion
            for emotion, score in positive_scores.items()
            if score >= max(self.min_score, top * self.min_ratio)
        ]

        primary = max(positive_scores, key=lambda k: positive_scores[k])
        if primary not in labels:
            labels.insert(0, primary)

        return {
            "primary": primary,
            "scores": {k: v for k, v in scores.items() if v > 0},
            "labels": labels,
            "confidence": round(min(1.0, top / 5.0), 3),
            "signals": signals,
            "language": self._detect_language(cleaned),
            "intensity": round(min(1.0, emoji_score + caps * 0.3), 3),
        }

    def analyze_many(self, texts: List[str]) -> List[Dict[str, object]]:
        return [self.analyze(text) for text in texts]

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _empty(detected_language: Optional[str] = None) -> Dict[str, object]:
        return {
            "primary": "neutral",
            "scores": {},
            "labels": ["neutral"],
            "confidence": 0.0,
            "signals": {},
            "language": detected_language or "unknown",
            "intensity": 0.0,
        }

    @staticmethod
    def _normalise(text: str) -> str:
        """Lower-case, strip accents and collapse whitespace."""
        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"\s+", " ", text)
        return f" {text} "

    def _context_multiplier(self, text: str, phrase: str) -> float:
        """Scale a phrase match by nearby intensifiers, negation and contrast."""
        index = text.find(phrase)
        if index == -1:
            return 1.0

        multiplier = 1.0
        window_start = max(0, index - 45)
        before = text[window_start:index]

        words = before.split()
        for word in reversed(words[-3:]):
            if word in _INTENSIFIERS:
                multiplier *= _INTENSIFIERS[word]
                break

        # Negation directly before the phrase flips it.
        for word in reversed(words):
            if word in _NEGATIONS:
                multiplier *= -0.75
                break
            if word not in {"the", "a", "an", "is", "was", "so", "very", "really"}:
                break

        # A contrast marker before the phrase means the complaint is the
        # point of the sentence - boost it.
        for marker in _CONTRAST_MARKERS:
            if marker in words[-4:]:
                multiplier *= 1.35
                break

        return multiplier

    @staticmethod
    def _emoji_signals(text: str):
        """Score emoji usage as an emotional intensity signal."""
        score = 0.0
        emotions: Dict[str, float] = {}

        for char in text:
            if char in _EMOJI_TRIGGERED:
                score += 0.22
                emotions["triggered"] = emotions.get("triggered", 0) + 0.55
            elif char in _EMOJI_LOVE:
                score += 0.18
                emotions["love"] = emotions.get("love", 0) + 0.5
            elif char in _EMOJI_NEGATIVE:
                score += 0.25
                emotions["hate"] = emotions.get("hate", 0) + 0.6

        return min(1.0, score), emotions

    @staticmethod
    def _caps_intensity(text: str) -> float:
        """0..1 - how shouty the comment is."""
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 8:
            return 0.0
        upper = sum(1 for c in letters if c.isupper())
        ratio = upper / len(letters)
        return 1.0 if ratio > 0.7 else 0.0

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect the script of a comment."""
        if any("஀" <= c <= "௿" for c in text):
            return "tamil"
        if any("ऀ" <= c <= "ॿ" for c in text):
            return "hindi"
        if any("ఀ" <= c <= "౿" for c in text):
            return "telugu"
        if any("가" <= c <= "힯" for c in text):
            return "korean"
        if any("一" <= c <= "鿿" for c in text):
            return "chinese"
        if any("؀" <= c <= "ۿ" for c in text):
            return "arabic"
        return "latin"
