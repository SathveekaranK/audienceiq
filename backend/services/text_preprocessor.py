"""
Text Preprocessing Module for AudienceIQ
Follows PRD Section 7.1: Text Preprocessing
Purpose: Prepare raw comments for NLP analysis
"""

import re
import string
from typing import List, Optional
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')

lemmatizer = WordNetLemmatizer()
english_stopwords = set(stopwords.words('english'))


def remove_html(text: str) -> str:
    """Remove HTML elements from text while preserving content."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove extra whitespace, normalize unicode."""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def handle_urls_mentions(text: str, remove_urls: bool = True, 
                         remove_mentions: bool = True) -> str:
    """Handle URLs and mentions in text.
    
    Preserves emojis and meaningful informal expressions.
    """
    # Replace URLs with placeholder (preserving position info)
    if remove_urls:
        text = re.sub(r'http\S+|www\S+|https\S+', '[URL]', text)
    
    # Replace mentions with placeholder
    if remove_mentions:
        text = re.sub(r'@\w+', '[MENTION]', text)
    
    return text


def tokenize_text(text: str) -> List[str]:
    """Tokenize text into words/tokens."""
    tokens = word_tokenize(text)
    return tokens


def remove_stopwords(tokens: List[str], language: str = 'english') -> List[str]:
    """Remove stopwords while preserving important tokens."""
    filtered = [t for t in tokens if t not in english_stopwords]
    return filtered


def lemmatize_tokens(tokens: List[str]) -> List[str]:
    """Lemmatize tokens to base form.
    
    Preserves emojis and special tokens by passing them through unchanged.
    """
    lemmatized = []
    for token in tokens:
        if token.isalpha() or token in emojis_known():
            lemmatized.append(lemmatizer.lemmatize(token))
        else:
            lemmatized.append(token)
    return lemmatized


def emojis_known() -> set:
    """Return set of known emoji patterns for preservation."""
    # Common emojis that should be preserved in analysis
    return {
        '😀', '😁', '😂', '😃', '😄', '😅', '😆', '😉', '😊', '😋',
        '😎', '😍', '😘', '😜', '😝', '😞', '😟', '😠', '😡', '😢',
        '😤', '😭', '😱', '😲', '🥺', '🥰', '💪', '👍', '👎', '❤️',
        '🔥', '💡', '💻', '📚', '🎓', '👨‍💻', '👩‍💻'
    }


def preprocess_comment(
    text: str,
    remove_html_flag: bool = True,
    normalize: bool = True,
    handle_urls: bool = True,
    handle_mentions: bool = True,
    remove_stopwords_flag: bool = True,
    lemmatize: bool = True
) -> str:
    """Full preprocessing pipeline for a single comment.
    
    Follows PRD 7.1 operations in order:
    1. Remove HTML elements
    2. Normalize text
    3. Handle URLs and mentions
    4. Tokenization
    5. Stopword removal
    6. Lemmatization
    7. Preserve emojis, negations, informal expressions
    """
    if not text or not text.strip():
        return ""
    
    processed = text
    
    # 1. Remove HTML elements
    if remove_html_flag:
        processed = remove_html(processed)
    
    # 2. Normalize text
    if normalize:
        processed = normalize_text(processed)
    
    # 3. Handle URLs and mentions (preserve emojis/informal expressions)
    processed = handle_urls_mentions(processed, remove_urls=handle_urls, 
                                      remove_mentions=handle_mentions)
    
    # 4. Tokenization
    tokens = tokenize_text(processed)
    
    # 5. Stopword removal
    if remove_stopwords_flag:
        tokens = remove_stopwords(tokens)
    
    # 6. Lemmatization
    if lemmatize:
        tokens = lemmatize_tokens(tokens)
    
    # Rejoin tokens, preserving emojis and special expressions
    result = ' '.join(tokens)
    
    return result


def extract_ngrams(text: str, n: int = 2, max_results: int = 10) -> List[str]:
    """Extract n-grams from text for topic detection."""
    tokens = preprocess_comment(text, lemmatize=False).split()
    ngrams = []
    
    for i in range(len(tokens) - n + 1):
        ngram = ' '.join(tokens[i:i+n])
        ngrams.append(ngram)
    
    # Sort by frequency and return top results
    from collections import Counter
    counter = Counter(ngrams)
    return [ngram for ngram, _ in counter.most_common(max_results)]


# Example usage
if __name__ == "__main__":
    sample_comment = "This tutorial on AI tools is 🔥 but too fast! Please make more [URL] examples."
    processed = preprocess_comment(sample_comment)
    print(f"Original: {sample_comment}")
    print(f"Processed: {processed}")