"""
Sentiment Analysis Module for AudienceIQ
Follows PRD Section 7.2: Sentiment Analysis
Purpose: Understand the emotional reaction of viewers
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import nltk

# Download VADER lexicon if not already downloaded
try:
    nltk.data.find('sentiment/vader')
except LookupError:
    nltk.download('vader_lexicon')

from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Try to import transformers for advanced sentiment
try:
    from transformers import pipeline
    _transformers_available = True
except ImportError:
    _transformers_available = False
    pipeline = None


@dataclass
class SentimentResult:
    """Structured sentiment analysis result."""
    label: str  # positive, negative, neutral
    score: float  # confidence score (-1 to 1 or 0 to 1)
    model_version: str
    text_processed: str


class VADERSentiment:
    """VADER baseline sentiment analysis."""
    
    def __init__(self):
        self._analyzer = SentimentIntensityAnalyzer()
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using VADER.
        
        VADER outputs:
        - compound score: normalized float between -1 (most negative) and +1 (most positive)
        - positive, negative, neutral probabilities
        """
        if not text or not text.strip():
            return SentimentResult(
                label="neutral",
                score=0.0,
                model_version="vader-baseline",
                text_processed=text or ""
            )
        
        scores = self._analyzer.polarity_scores(text)
        
        # Determine label based on compound score
        compound = scores['compound']
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        # Use compound score as the confidence score
        # Transform to 0-1 scale for consistency
        score = (compound + 1) / 2  # Map -1 to 1 → 0 to 1
        
        return SentimentResult(
            label=label,
            score=round(score, 4),
            model_version="vader-baseline",
            text_processed=text
        )


class TransformerSentiment:
    """Fine-tuned transformer model for sentiment analysis."""
    
    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment"):
        self.model_name = model_name
        self._classifier = None
        
        if _transformers_available:
            try:
                self._classifier = pipeline(
                    "sentiment-analysis", 
                    model=model_name,
                    device=0 if __import__('torch').cuda.is_available() else -1
                )
            except Exception:
                self._classifier = None
    
    def analyze(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment using transformer model."""
        if not text or not text.strip():
            return None
        
        if self._classifier is None:
            # Fall back to VADER
            vader = VADERSentiment()
            return vader.analyze(text)
        
        try:
            # Transformers pipeline returns list of dicts
            results = self._classifier(text[:512])  # Truncate if too long
            
            if isinstance(results, list) and len(results) > 0:
                result = results[0]
                # Format: {'label': 'POSITIVE', 'score': 0.95}
                label = result['label'].lower()
                score = result['score']
                
                # Map labels if needed
                if label in ['pos', 'positive']:
                    final_label = "positive"
                elif label in ['neg', 'negative']:
                    final_label = "negative"
                else:
                    final_label = "neutral"
                
                # Score is already 0-1
                return SentimentResult(
                    label=final_label,
                    score=round(float(score), 4),
                    model_version=self.model_name,
                    text_processed=text
                )
        except Exception:
            pass
        
        # Fall back to VADER
        vader = VADERSentiment()
        return vader.analyze(text)


class SentimentAnalyzer:
    """Composite sentiment analyzer that uses VADER by default with transformer fallback."""
    
    def __init__(self, use_transformer: bool = False):
        self.vader = VADERSentiment()
        self.use_transformer = use_transformer
        self.transformer = TransformerSentiment() if use_transformer else None
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment, preferring transformer if available."""
        if self.use_transformer and self.transformer:
            result = self.transformer.analyze(text)
            if result is not None:
                return result
        
        # Fall back to VADER
        return self.vader.analyze(text)
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze sentiment for a batch of texts."""
        results = []
        for text in texts:
            result = self.analyze(text)
            results.append(result)
        return results


# Example usage and testing
if __name__ == "__main__":
    analyzer = SentimentAnalyzer(use_transformer=False)
    
    test_comments = [
        "I love this tutorial! So helpful and clear 😍",
        "This was too fast, I couldn't follow 😤",
        "The video was okay, nothing special",
        "Best AI explanation I've seen this year!"
    ]
    
    for comment in test_comments:
        result = analyzer.analyze(comment)
        print(f"Comment: {comment[:50]}...")
        print(f"  Sentiment: {result.label}, Score: {result.score}")
        print()