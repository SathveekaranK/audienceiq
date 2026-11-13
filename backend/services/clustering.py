"""
Clustering Module for AudienceIQ
Follows PRD Section 7.4: Clustering
Purpose: Identify groups with similar discussion interests
"""

from typing import List, Dict, Any, Optional, Tuple
import string
import numpy as np

# ---- Optional dependency handling -----------------------------------------
# scikit-learn is required for clustering; umap-learn is optional (only used
# for 2D visualisation of the clusters).
try:
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import silhouette_score
    KMeansAvailable = True
except ImportError:  # pragma: no cover - exercised only without sklearn
    KMeansAvailable = False

try:
    from sklearn.manifold import TSNE
    TSNEAvailable = True
except ImportError:  # pragma: no cover
    TSNEAvailable = False

try:
    import umap.umap_ as umap
    UMAPAvailable = True
except ImportError:  # pragma: no cover
    umap = None
    UMAPAvailable = False


def check_dependencies():
    """Raise a helpful error if scikit-learn is not installed."""
    if not KMeansAvailable:
        raise ImportError(
            "scikit-learn is required for clustering. Install it with: pip install scikit-learn"
        )


class KMeansClusterer:
    """K-Means clustering for audience segmentation."""
    
    def __init__(self, n_clusters: int = 5, random_state: int = 42,
                 max_iter: int = 300, n_init: int = 10):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.max_iter = max_iter
        self.n_init = n_init
        self.model = None
        self.labels = None
        self.cluster_centers = None
        self.inertia = None
        
        if not KMeansAvailable:
            check_dependencies()
    
    def fit(self, embeddings: np.ndarray) -> 'KMeansClusterer':
        """Fit K-Means clustering to comment embeddings."""
        if embeddings is None or len(embeddings) == 0:
            return self
        
        n_samples = len(embeddings)
        # Adjust n_clusters if there are fewer samples than clusters
        actual_n_clusters = min(self.n_clusters, max(1, n_samples // 2))
        
        self.model = KMeans(
            n_clusters=actual_n_clusters,
            random_state=self.random_state,
            max_iter=self.max_iter,
            n_init=self.n_init
        )
        
        self.labels = self.model.fit_predict(embeddings)
        self.cluster_centers = self.model.cluster_centers_
        self.inertia = self.model.inertia_
        
        return self
    
    def get_cluster_sizes(self) -> Dict[int, int]:
        """Get the size of each cluster."""
        if self.labels is None:
            return {}
        
        sizes = {}
        for label in set(self.labels):
            sizes[label] = int(np.sum(self.labels == label))
        return sizes
    
    def get_cluster_centers(self) -> np.ndarray:
        """Get cluster centroids."""
        return self.cluster_centers
    
    def calculate_silhouette(self, embeddings: np.ndarray) -> Optional[float]:
        """Calculate silhouette score for optimal cluster count."""
        if self.labels is None or len(set(self.labels)) < 2:
            return None
        
        try:
            score = silhouette_score(embeddings, self.labels)
            return round(float(score), 4)
        except Exception:
            return None


class DBSCANClusterer:
    """DBSCAN clustering for audience segmentation."""
    
    def __init__(self, eps: float = 0.5, min_samples: int = 5,
                 min_cluster_size: int = 5):
        self.eps = eps
        self.min_samples = min_samples
        self.min_cluster_size = min_cluster_size
        self.model = None
        self.labels = None
        
        if not KMeansAvailable:
            check_dependencies()
    
    def fit(self, embeddings: np.ndarray) -> 'DBSCANClusterer':
        """Fit DBSCAN clustering to comment embeddings."""
        if embeddings is None or len(embeddings) == 0:
            return self
        
        self.model = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            min_cluster_size=self.min_cluster_size
        )
        
        self.labels = self.model.fit_predict(embeddings)
        
        return self
    
    def get_cluster_sizes(self) -> Dict[int, int]:
        """Get the size of each cluster (excluding noise)."""
        if self.labels is None:
            return {}
        
        # Exclude noise (label = -1)
        valid_labels = [l for l in set(self.labels) if l != -1]
        sizes = {}
        for label in valid_labels:
            sizes[label] = int(np.sum(self.labels == label))
        
        # Count noise points
        if -1 in set(self.labels):
            sizes[-1] = int(np.sum(self.labels == -1))
        
        return sizes


class UMAPReducer:
    """UMAP dimensionality reduction for visualization."""
    
    def __init__(self, n_components: int = 2, n_neighbors: int = 15,
                 min_dist: float = 0.0, metric: str = 'cosine'):
        self.n_components = n_components
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.metric = metric
    
    def reduce(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce embeddings to lower dimensions for visualization."""
        if embeddings is None or len(embeddings) == 0:
            return np.array([])
        
        # Check if we need more components than requested for t-SNE/UMAP
        n_samples = len(embeddings)
        actual_components = min(self.n_components, n_samples - 1, embeddings.shape[1])
        
        if actual_components < 1:
            return embeddings[:, :1]
        
        try:
            reducer = umap.UMAP(
                n_components=actual_components,
                n_neighbors=self.n_neighbors,
                min_dist=self.min_dist,
                metric=self.metric,
                random_state=42
            )
            
            reduced = reducer.fit_transform(embeddings)
            return reduced
        except Exception:
            # Fallback: just take first components
            return embeddings[:, :actual_components]


class TSNEReducer:
    """t-SNE dimensionality reduction for visualization."""
    
    def __init__(self, n_components: int = 2, perplexity: int = 30,
                 learning_rate: str = 'auto', random_state: int = 42):
        self.n_components = n_components
        self.perplexity = perplexity
        self.learning_rate = learning_rate
        self.random_state = random_state
    
    def reduce(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce embeddings to lower dimensions using t-SNE."""
        if embeddings is None or len(embeddings) == 0:
            return np.array([])
        
        n_samples = len(embeddings)
        # Perplexity should be less than number of samples
        actual_perplexity = min(self.perplexity, max(1, n_samples // 3))
        
        try:
            from sklearn.manifold import TSNE
            reducer = TSNE(
                n_components=self.n_components,
                perplexity=actual_perplexity,
                learning_rate=self.learning_rate,
                random_state=self.random_state
            )
            
            reduced = reducer.fit_transform(embeddings)
            return reduced
        except Exception:
            # Fallback: just take first two components
            return embeddings[:, :2] if embeddings.shape[1] >= 2 else embeddings


class AudienceSegmenter:
    """Composite audience segmentation using clustering."""
    
    def __init__(self, n_clusters: int = 5, use_umap: bool = True,
                 use_dbscan: bool = False):
        self.n_clusters = n_clusters
        self.use_umap = use_umap
        self.use_dbscan = use_dbscan
        self.kmeans = KMeansClusterer(n_clusters=n_clusters)
        self.dbscan = DBSCANClusterer()
        self.umap_reducer = UMAPReducer() if use_umap else None
        self.tsne_reducer = TSNEReducer()
    
    def segment(self, embeddings: np.ndarray, 
                document_texts: List[str] = None) -> Dict[str, Any]:
        """Perform audience segmentation on comment embeddings."""
        if embeddings is None or len(embeddings) == 0:
            return {'labels': [], 'centers': [], 'method': 'none'}
        
        # Choose clustering method
        if self.use_dbscan:
            self.dbscan.fit(embeddings)
            labels = self.dbscan.labels
            method = 'dbscan'
        else:
            self.kmeans.fit(embeddings)
            labels = self.kmeans.labels
            method = 'kmeans'
        
        # Reduce dimensions for analysis/visualization
        if self.umap_reducer:
            reduced = self.umap_reducer.reduce(embeddings)
        else:
            reduced = self.tsne_reducer.reduce(embeddings)
        
        # Get cluster sizes
        cluster_sizes = self.kmeans.get_cluster_sizes() if not self.use_dbscan \
            else self.dbscan.get_cluster_sizes()
        
        # Analyze cluster keywords if document texts provided
        cluster_keywords = {}
        if document_texts and len(document_texts) == len(embeddings):
            cluster_keywords = self._analyze_cluster_keywords(
                document_texts, labels
            )
        
        return {
            'labels': labels.tolist(),
            'cluster_sizes': cluster_sizes,
            'method': method,
            'reduced_embeddings': reduced.tolist() if hasattr(reduced, 'tolist') else reduced,
            'cluster_centers': self.kmeans.get_cluster_centers().tolist() 
                if self.kmeans.cluster_centers is not None else None,
            'cluster_keywords': cluster_keywords,
            'silhouette_score': self.kmeans.calculate_silhouette(embeddings)
        }
    
    def _analyze_cluster_keywords(self, texts: List[str], labels: np.ndarray) -> Dict[int, List[str]]:
        """Extract representative keywords for each cluster."""
        cluster_keywords = {}
        
        for cluster_id in set(labels):
            if cluster_id == -1:  # Skip noise in DBSCAN
                continue
            
            # Get texts belonging to this cluster
            cluster_texts = [texts[i] for i in range(len(texts)) if labels[i] == cluster_id]
            
            if not cluster_texts:
                continue
            
            # Simple keyword frequency analysis
            from collections import Counter
            all_words = []
            for text in cluster_texts:
                words = text.lower().split()
                # Filter simple tokens
                words = [w.strip(string.punctuation) for w in words if w.isalpha()]
                all_words.extend(words)
            
            # Get top words
            top_words = Counter(all_words).most_common(5)
            cluster_keywords[cluster_id] = [word for word, _ in top_words]
        
        return cluster_keywords


# Example usage
if __name__ == "__main__":
    # Sample embeddings (in practice, these would be sentence transformer embeddings)
    sample_embeddings = np.random.rand(20, 768)
    sample_texts = [
        "I love AI tutorials, they're so helpful!",
        "Python coding is great for beginners.",
        "Machine learning models are complex.",
        "Need more practical demonstrations.",
        "Advanced AI concepts are too difficult.",
        "Tutorials move too fast for me.",
        "Great resources for learning programming.",
        "AI tools help automate my work.",
        "Career opportunities in tech are expanding.",
        "Free learning resources are valuable.",
        "Beginner tutorials need more examples.",
        "Developers want advanced AI concepts.",
        "Students explore career in technology.",
        "AI tools for automation are growing.",
        "Programming tutorials are too theoretical.",
        "Practical projects help understanding.",
        "More tutorials on machine learning needed.",
        "Tech career guidance is helpful.",
        "Free resources for skill development.",
        "Beginner-friendly content is rare."
    ]
    
    segmenter = AudienceSegmenter(n_clusters=4, use_dbscan=False)
    result = segmenter.segment(sample_embeddings, sample_texts)
    
    print(f"Clustering method: {result['method']}")
    print(f"Cluster sizes: {result['cluster_sizes']}")
    print(f"Silhouette score: {result['silhouette_score']}")
    print(f"\nCluster keywords:")
    for cluster_id, keywords in result['cluster_keywords'].items():
        print(f"  Cluster {cluster_id}: {keywords}")