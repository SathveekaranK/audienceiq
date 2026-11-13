"""
Topic Modeling Module for AudienceIQ
Follows PRD Section 7.3: Topic Modelling
Purpose: Discover the major subjects discussed by audiences
"""

from typing import List, Dict, Tuple, Optional, Any
from collections import Counter
import math
import re
import numpy as np

# Word-ish tokens from any script: letters, digits and apostrophes.
_WORD_RE = re.compile(r"[\w'’]+", re.UNICODE)

# Words that carry no topic meaning on their own.
_STOPWORDS = {
    "the", "and", "for", "this", "that", "you", "your", "are", "was", "were",
    "but", "not", "with", "have", "has", "had", "can", "will", "just", "really",
    "very", "too", "also", "get", "got", "one", "all", "how", "why", "what",
    "when", "where", "who", "there", "here", "they", "them", "their", "its",
    "i'm", "im", "i've", "ive", "dont", "don't", "cant", "can't", "didnt",
    "didn't", "would", "could", "should", "from", "about", "into", "than",
    "then", "some", "more", "most", "like", "video", "comment", "please",
    "is", "am", "be", "been", "being", "do", "does", "did", "so", "no", "yes",
    "my", "me", "i", "we", "us", "our", "he", "she", "his", "her", "you",
    "am", "any", "each", "more", "other", "such", "only", "own", "same",
    "too", "very", "just", "now", "new", "one", "two", "out", "up", "down",
    "off", "over", "under", "again", "still", "even", "because", "while",
    "if", "or", "as", "at", "by", "in", "on", "to", "of", "is", "am", "it",
    "he", "we", "us", "am", "im", "its", "da", "ku", "la", "na", "va",
}


def _is_non_latin_corpus(documents: List[str]) -> bool:
    """True when the comments are mainly written in a non-Latin script."""
    sample = " ".join(documents[:200])
    if not sample:
        return False

    latin = 0
    other = 0
    for char in sample:
        if char.isalpha():
            if "a" <= char.lower() <= "z":
                latin += 1
            else:
                other += 1

    return other > latin


def _tokenize(text: str) -> List[str]:
    """Split text into meaningful words, whatever the script."""
    tokens = []
    for raw in _WORD_RE.findall(text or ""):
        token = raw.strip("'’").lower()
        if not token:
            continue
        if token in _STOPWORDS:
            continue
        if token.isdigit():
            continue

        # Non-Latin scripts pack a lot of meaning into 2 characters, but
        # those are usually grammatical particles rather than topic words.
        has_non_latin = any(
            c.isalpha() and not ("a" <= c.lower() <= "z") for c in token
        )
        if has_non_latin:
            if len(token) < 3:
                continue
        elif len(token) < 2:
            continue

        tokens.append(token)
    return tokens


def describe_topics(
    documents: List[str],
    distributions: List[List[float]],
    topics: List[Dict[str, Any]],
    top_words: int = 5,
) -> List[Dict[str, Any]]:
    """Give every topic a readable name built from the words people used.

    The LDA model itself works on n-grams, so its raw terms are not things a
    human would recognise. Instead we look at the comments that belong to
    each topic and name it after the words that are *distinctive* to that
    topic - scored with an IDF so words common to the whole channel do not
    end up as the label.
    """
    tokenized = [_tokenize(document) for document in documents]
    corpus_size = max(1, len(documents))

    # How many comments in the whole corpus mention each word.
    global_df: Counter = Counter()
    for tokens in tokenized:
        global_df.update(set(tokens))

    # Which comments belong to which topic.
    buckets: Dict[int, List[int]] = {}
    for index, distribution in enumerate(distributions):
        if index >= len(documents) or not distribution:
            continue
        best = max(range(len(distribution)), key=lambda i: distribution[i] or 0)
        if (distribution[best] or 0) <= 0:
            continue
        buckets.setdefault(best, []).append(index)

    described = []
    for index, topic in enumerate(topics):
        member_indexes = buckets.get(index, [])
        if not member_indexes:
            # A topic nobody was assigned to carries no signal.
            continue

        local: Counter = Counter()
        for i in member_indexes:
            local.update(set(tokenized[i]))

        # Score by local frequency weighted by how rare the word is overall.
        scored = []
        for word, count in local.items():
            df = global_df.get(word, 1)
            if df > corpus_size * 0.5:
                # Present in most of the channel - not distinctive.
                continue
            idf = math.log((corpus_size + 1) / (df + 1)) + 1.0
            scored.append((word, count * idf))

        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        words = [word for word, _ in scored[:top_words]]

        described.append({
            **topic,
            'name': words[0] if words else f"Topic {index + 1}",
            'display_words': words,
            'document_count': len(member_indexes),
            'sample_documents': [documents[i] for i in member_indexes[:3]],
        })

    return described

# Try to import topic modeling libraries
try:
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation as LDA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LDA = None
    TfidfVectorizer = None
    CountVectorizer = None

try:
    import bertopic
    from bertopic import BERTopic
    BERTOPIC_AVAILABLE = True
except ImportError:
    BERTOPIC_AVAILABLE = False
    BERTopic = None


class LDATopicModel:
    """LDA (Latent Dirichlet Allocation) topic model."""
    
    def __init__(self, n_topics: int = 5, max_df: float = 0.9, 
                 min_df: int = 1, random_state: int = 42):
        self.n_topics = n_topics
        self.max_df = max_df
        self.min_df = min_df
        self.random_state = random_state
        self.model = None
        self.vectorizer = None
        self.feature_names = None
        self.char_mode = False
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for LDA topic modeling")
    
    def fit(self, documents: List[str]) -> 'LDATopicModel':
        """Fit LDA topic model to documents."""
        if not documents:
            return self
        
        # Vectorize documents. For scripts without word spacing (Tamil,
        # Hindi, Chinese, ...) word tokens are unreliable, so we fall back
        # to character n-grams which work in any script.
        self.char_mode = _is_non_latin_corpus(documents)
        
        if self.char_mode:
            self.vectorizer = TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=(2, 4),
                min_df=1,
                max_features=400,
                lowercase=True,
            )
        else:
            self.vectorizer = CountVectorizer(
                max_df=self.max_df,
                min_df=self.min_df,
                stop_words='english',
                lowercase=True,
                # Drop single characters - they are noise in short comments.
                token_pattern=r"(?u)\b\w[\w']+\b",
            )
        
        doc_term_matrix = self.vectorizer.fit_transform(documents)
        self.feature_names = self.vectorizer.get_feature_names_out()
        
        # Fit LDA
        self.model = LDA(
            n_components=self.n_topics,
            random_state=self.random_state,
            learning_method='online',
            max_iter=10,
            learning_decay=0.7,
            batch_size=128
        )
        
        self.model.fit(doc_term_matrix)
        
        return self
    
    def get_topics(self, n_top_words: int = 10) -> List[Dict[str, Any]]:
        """Get discovered topics with top words and relevance."""
        if self.model is None or self.vectorizer is None:
            return []
        
        topics = []
        for topic_idx, topic in enumerate(self.model.components_):
            top_indices = topic.argsort()[:-n_top_words - 1:-1]
            top_words = [(self.feature_names[i], topic[i]) for i in top_indices]
            topics.append({
                'topic_id': topic_idx,
                'top_words': top_words,
                'relevance_scores': [float(w) for _, w in top_words]
            })
        
        return topics
    
    def transform_documents(self, documents: List[str]) -> np.ndarray:
        """Transform documents to topic distributions."""
        if self.model is None or self.vectorizer is None:
            return np.zeros((len(documents), self.n_topics))
        
        doc_term_matrix = self.vectorizer.transform(documents)
        topic_distributions = self.model.transform(doc_term_matrix)
        return topic_distributions


class BERTopicModel:
    """BERTopic advanced topic modeling."""
    
    def __init__(self, language: str = "english",
                 nr_topics: int = None,
                 min_topic_size: int = 10):
        self.language = language
        self.nr_topics = nr_topics
        self.min_topic_size = min_topic_size
        self.model = None
        
        if not BERTOPIC_AVAILABLE:
            raise ImportError("BERTopic is required for advanced topic modeling")
    
    def fit(self, documents: List[str]) -> 'BERTopicModel':
        """Fit BERTopic model to documents."""
        if not documents:
            return self
        
        try:
            self.model = BERTopic(
                language=self.language,
                nr_topics=self.nr_topics,
                min_topic_size=self.min_topic_size,
                calculate_probabilities=True,
                verbose=False
            )
            
            topics, self.document_probs = self.model.fit_transform(documents)
            
            # Get topic information
            if self.model:
                topic_info = self.model.get_topic_info()
                self.topics = topics
                self.topic_info = topic_info
        except Exception:
            # Fall back to LDA if BERTopic fails
            try:
                lda = LDATopicModel(n_topics=5)
                lda.fit(documents)
                self.model = lda.model
                self.topic_info = lda.get_topics()
            except Exception:
                pass
        
        return self
    
    def get_topics(self, n_top_words: int = 10) -> List[Dict[str, Any]]:
        """Get discovered topics with top words."""
        if self.model is None or not hasattr(self, 'topic_info'):
            return []
        
        topic_info = self.topic_info if hasattr(self, 'topic_info') else []
        
        # Filter out default/-1 topic
        valid_topics = topic_info[
            topic_info['Topic'] >= 0
        ] if 'Topic' in topic_info.columns else topic_info
        
        topics = []
        for _, row in valid_topics.head(self.nr_topics or 5).iterrows():
            topic_id = row['Topic']
            # Get top words for this topic
            if self.model:
                topic_words = self.model.get_topic(topic_id)[:n_top_words]
                topics.append({
                    'topic_id': topic_id,
                    'name': row['Name'] if 'Name' in row.index else f"Topic {topic_id}",
                    'top_words': topic_words,
                    'probability': row['Probability'] if 'Probability' in row.index else 1.0
                })
        
        return topics


class TopicDetector:
    """Composite topic detection using multiple approaches."""
    
    def __init__(self, use_bertopic: bool = False, n_topics: int = 5):
        self.use_bertopic = use_bertopic
        self.n_topics = n_topics
        self.lda = LDATopicModel(n_topics=n_topics) if not use_bertopic else None
        self.bertopic = BERTopicModel(nr_topics=n_topics) if use_bertopic else None
    
    def detect_topics(self, documents: List[str]) -> Dict[str, Any]:
        """Detect topics from document collection."""
        if not documents:
            return {'topics': [], 'document_distributions': []}
        
        # Try BERTopic first if requested
        if self.use_bertopic and self.bertopic:
            self.bertopic.fit(documents)
            topics = self.bertopic.get_topics(n_top_words=10)
            document_dists = (
                self.bertopic.model.transform(
                    self.bertopic.model.vectorizer.transform(documents)
                ) if self.bertopic.model else []
            )
            
            bertopic_distributions = (
                document_dists.tolist()
                if getattr(document_dists, "size", 0)
                else []
            )
            topics = describe_topics(documents, bertopic_distributions, topics)
            
            return {
                'topics': topics,
                'document_distributions': bertopic_distributions,
                'method': 'BERTopic'
            }
        
        # Fall back to LDA
        if self.lda:
            self.lda.fit(documents)
            topics = self.lda.get_topics(n_top_words=10)
            document_dists = self.lda.transform_documents(documents)
            distributions = (
                document_dists.tolist()
                if getattr(document_dists, "size", 0)
                else []
            )
            
            # Name each topic after the words people actually used.
            topics = describe_topics(documents, distributions, topics)
            
            return {
                'topics': topics,
                'document_distributions': distributions,
                'method': 'LDA'
            }
        
        # Basic fallback: keyword-based topic detection
        return self._keyword_based_topics(documents)
    
    def _keyword_based_topics(self, documents: List[str]) -> Dict[str, Any]:
        """Fallback keyword-based topic detection."""
        # Define common tech/education topics
        topic_keywords = {
            'ai_artificial_intelligence': [
                'ai', 'artificial intelligence', 'machine learning', 'deep learning',
                'neural network', 'gpt', 'chatgpt', 'llm'
            ],
            'programming': [
                'python', 'javascript', 'code', 'programming', 'development',
                'web', 'app', 'software', 'debug'
            ],
            'career': [
                'career', 'job', 'employment', 'interview', 'salary',
                'promotion', 'skill', 'certification'
            ],
            'learning_resources': [
                'tutorial', 'learning', 'course', 'resource', 'ebook',
                'video', 'guide', 'training'
            ],
            'technology_tools': [
                'tool', 'software', 'application', 'platform', 'system',
                'automation', 'framework', 'library'
            ]
        }
        
        # Score documents against topics
        document_topics = []
        for doc in documents:
            doc_lower = doc.lower()
            scores = {}
            for topic, keywords in topic_keywords.items():
                score = sum(1 for kw in keywords if kw in doc_lower)
                if score > 0:
                    scores[topic] = score
            
            # Get top topic for this document
            if scores:
                top_topic = max(scores, key=scores.get)
                document_topics.append(top_topic)
            else:
                document_topics.append('general')
        
        # Calculate topic frequencies
        topic_freq = Counter(document_topics)
        
        topics = []
        for topic_name, freq in topic_freq.most_common(len(topic_keywords)):
            topics.append({
                'topic_id': topic_name,
                'name': topic_name.replace('_', ' ').title(),
                'top_words': [(kw, 1.0) for kw in topic_keywords.get(topic_name, [])[:5]],
                'relevance_scores': [1.0] * min(5, len(topic_keywords.get(topic_name, []))),
                'document_count': freq
            })
        
        return {
            'topics': topics,
            'document_distributions': [[1.0 if i == list(topic_freq.keys()).index(topic_name) else 0.0 
                                       for i in range(len(topic_freq))] 
                                      for topic_name in [t['topic_id'] for t in topics]],
            'method': 'Keyword-based'
        }


# Example usage
if __name__ == "__main__":
    sample_documents = [
        "I learned so much about AI and machine learning in this video!",
        "Great Python tutorial, very helpful for beginners.",
        "The instructor explained career opportunities well.",
        "Need more tutorials on deep learning and neural networks.",
        "Good resource for learning Python programming basics."
    ]
    
    detector = TopicDetector(use_bertopic=False, n_topics=3)
    result = detector.detect_topics(sample_documents)
    
    print("Detected Topics:")
    for topic in result['topics']:
        print(f"  {topic['name']}: {[(w, round(s, 3)) for w, s in topic['top_words']]}")
        print(f"  Document count: {topic['document_count']}")
    print(f"\nMethod: {result['method']}")