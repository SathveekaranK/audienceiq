"""Main API Router for AudienceIQ"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
from datetime import datetime

from pydantic import BaseModel, Field

from auth import (
    create_session,
    get_current_session,
    get_current_user,
    require_comment_access,
    require_creator_access,
    require_post_access,
)
from database import get_db
from sqlalchemy.orm import Session
from services import text_preprocessor, sentiment_analyzer, topic_modeler, clustering
from models import (
    User, Creator, UserCreator, Post, Commenter, Comment,
    SentimentResult, Topic, CommentTopic, AudienceSegment,
    SegmentComment, ContentRequest, Report, AnalysisRun, AuthSession
)

logger = logging.getLogger("audienceiq.api")

router = APIRouter(prefix="/api/v1", tags=["AudienceIQ"])


# ---------------------------------------------------------------------------
# Request models
#
# Credentials must travel in the JSON body - FastAPI treats bare `str`
# parameters as query parameters, which would put the password in the URL,
# the browser history and the access logs.
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=72)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=72)


# A fixed bcrypt hash used when the username does not exist, so that failed
# logins take the same amount of time whether or not the user is real
# (otherwise the response time leaks which usernames are registered).
_DUMMY_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.7uOhPnI3dUX8iEyHNLm3Ph0R7QVn3Fa"


def _check_password(password: str, hashed: str) -> bool:
    """Compare a password against a hash, always doing the bcrypt work."""
    from bcrypt import checkpw

    try:
        return checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # pragma: no cover - malformed hash in the database
        return False


def _rate_limit(request: Request, bucket: str, limit: int, window_seconds: int) -> bool:
    """Very small in-process rate limiter.

    Returns True when the request is allowed. This is not a replacement for
    a shared limiter (Redis/memcached) but it stops the obvious brute-force
    and cost-amplification loops on a single-node deployment.
    """
    import time

    client = request.client.host if request.client else "unknown"
    now = time.time()
    store = getattr(request.app.state, "_rate_limits", None)
    if store is None:
        store = {}
        request.app.state._rate_limits = store

    key = (bucket, client)
    hits = [t for t in store.get(key, []) if now - t < window_seconds]
    if len(hits) >= limit:
        store[key] = hits
        return False
    hits.append(now)
    store[key] = hits
    return True



def _json_safe(value):
    """Convert numpy scalars/arrays into plain Python types for JSON output."""
    import numpy as np

    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _build_embeddings(texts: List[str]):
    """Turn raw comment text into a numeric matrix for clustering.

    Uses TF-IDF over the processed text, which is fast, dependency-light and
    produces meaningful groupings for short comments like YouTube ones.
    """
    import numpy as np

    clean = [t for t in texts if t and t.strip()]
    if not clean:
        return np.zeros((len(texts), 1))

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(
            max_features=300,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        matrix = vectorizer.fit_transform(clean).toarray()
    except Exception:
        # Fallback: simple bag-of-words so clustering still works.
        vocabulary: dict = {}
        rows = []
        for text in clean:
            counts = {}
            for word in text.lower().split():
                word = word.strip(".,!?;:\"'()[]{}")
                if not word:
                    continue
                if word not in vocabulary:
                    vocabulary[word] = len(vocabulary)
                counts[vocabulary[word]] = counts.get(vocabulary[word], 0) + 1
            row = [0.0] * len(vocabulary)
            for idx, count in counts.items():
                row[idx] = float(count)
            rows.append(row)

        width = max(len(vocabulary), 1)
        matrix = np.zeros((len(rows), width))
        for i, row in enumerate(rows):
            matrix[i, : len(row)] = row

    # L2-normalise so cosine-like distances behave sensibly for K-Means.
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    if matrix.shape[0] < len(texts):
        # Some texts were empty - pad so row order still lines up with comments.
        padding = np.zeros((len(texts) - matrix.shape[0], matrix.shape[1]))
        matrix = np.vstack([matrix, padding])

    return matrix


# ===== AUTHENTICATION ENDPOINTS =====

@router.post("/auth/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """User registration endpoint."""
    if not _rate_limit(request, "register", limit=10, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many accounts created from this address. Try again later.",
        )

    username = payload.username.strip()
    email = payload.email.strip()
    password = payload.password

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required",
        )
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email address is required",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    if len(password.encode("utf-8")) > 72:
        # bcrypt silently ignores everything past 72 bytes.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at most 72 bytes",
        )

    # Check if user exists
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        # Do not reveal whether the username *or* the email is the one that
        # already exists - that would allow account enumeration.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create account with those details"
        )

    # Create new user
    from bcrypt import hashpw, gensalt
    hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

    new_user = User(
        username=username,
        email=email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_session(db, new_user)
    return {
        "message": "User registered successfully",
        "user_id": new_user.user_id,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """User login endpoint."""
    if not _rate_limit(request, "login", limit=10, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a few minutes.",
        )

    username = payload.username.strip()
    password = payload.password

    user = db.query(User).filter(User.username == username).first()

    # Always run the bcrypt comparison - against a dummy hash when the user
    # does not exist - so the response time does not leak which usernames
    # are registered.
    password_ok = _check_password(
        password,
        user.password_hash if user else _DUMMY_HASH,
    ) and user is not None

    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_session(db, user)
    return {
        "message": "Login successful",
        "user_id": user.user_id,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/auth/logout")
async def logout(
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Invalidate the current bearer session."""
    db.delete(auth_session)
    db.commit()
    return {"message": "Logged out"}


# ===== CREATOR DISCOVERY (FR-01) =====

@router.get("/creators/search")
async def search_creators(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for YouTube channels."""
    # This would integrate with YouTube Data API v3
    # For now, search in local database
    creators = db.query(Creator).join(UserCreator).filter(
        UserCreator.user_id == current_user.user_id,
        Creator.creator_name.contains(query),
    ).limit(10).all()
    
    return {
        "creators": [
            {
                "creator_id": c.creator_id,
                "name": c.creator_name,
                "description": c.description,
                "profile_image": c.profile_image,
                "platform_type": c.platform_type
            }
            for c in creators
        ]
    }


@router.post("/creators/add")
async def add_creator(
    creator_name: str,
    platform_type: str = "youtube",
    platform_id: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a creator to user's list."""
    # Check if creator already exists
    existing = db.query(Creator).filter(
        Creator.platform_id == platform_id,
        Creator.platform_type == platform_type
    ).first()
    
    if existing:
        creator_id = existing.creator_id
    else:
        creator = Creator(
            creator_name=creator_name,
            platform_type=platform_type,
            platform_id=platform_id
        )
        db.add(creator)
        db.commit()
        db.refresh(creator)
        creator_id = creator.creator_id
    
    # Link user to creator without creating duplicate workspace rows.
    if not db.query(UserCreator).filter(
        UserCreator.user_id == current_user.user_id,
        UserCreator.creator_id == creator_id,
    ).first():
        db.add(UserCreator(user_id=current_user.user_id, creator_id=creator_id))
        db.commit()
    
    return {"message": "Creator added successfully", "creator_id": creator_id}


# ===== CONTENT SELECTION (FR-02) =====

# NOTE: GET /creators/{creator_id}/videos lives in routes/insights.py, which
# returns richer per-video stats (sentiment breakdown included).


# ===== COMMENT COLLECTION (FR-03) =====

@router.post("/comments/collect/{post_id}")
async def collect_comments(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Collect comments for a specific post.
    
    Would integrate with YouTube Data API to retrieve comments.
    """
    post = require_post_access(db, current_user, post_id)
    
    # In a real implementation, this would call YouTube API
    # For now, simulate comment collection
    from services import text_preprocessor
    
    # Example comments (would come from the YouTube Data API).
    # These are intentionally different from the seeded demo comments so the
    # dashboard never shows the same text twice.
    sample_comments = [
        "Really clear walkthrough, the diagrams helped a lot.",
        "Could you do a follow up on deploying this to production?",
        "Loved the structure of this lesson, very easy to follow along.",
        "The API section went a bit fast, maybe slow that down next time?",
        "Any chance of a transcript for the second half?",
    ]
    
    collected = []
    for i, comment_text in enumerate(sample_comments):
        # Preprocess the comment
        processed = text_preprocessor.preprocess_comment(comment_text)
        
        # Check if comment already exists (by platform id, or by text so we do
        # not create a near-duplicate of a comment already on this video).
        existing = db.query(Comment).filter(
            Comment.post_id == post_id,
            (Comment.platform_comment_id == f"yt_{post_id}_{i}")
            | (Comment.comment_text == comment_text),
        ).first()
        
        if existing:
            collected.append({
                "comment_id": existing.comment_id,
                "text": existing.comment_text,
                "processed_text": existing.processed_text or existing.comment_text
            })
            continue
        
        # Create comment (simulated YouTube comment)
        comment = Comment(
            platform_comment_id=f"yt_{post_id}_{i}",
            post_id=post_id,
            commenter_id=None,  # Would be populated from API
            parent_comment_id=None,
            comment_text=comment_text,
            processed_text=processed,
            like_count=i + 1,
            published_at=post.published_at,  # Would use actual comment timestamp
            collected_at=datetime.utcnow()
        )
        
        db.add(comment)
        collected.append({
            "comment_id": comment.comment_id,
            "text": comment_text,
            "processed_text": processed
        })
    
    db.commit()
    
    return {
        "message": f"Collected {len(collected)} comments",
        "comments": collected
    }


# ===== SENTIMENT ANALYSIS (FR-04) =====

@router.post("/analysis/sentiment/{comment_id}")
async def analyze_sentiment(
    comment_id: int,
    use_transformer: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze sentiment for a comment."""
    comment = require_comment_access(db, current_user, comment_id)
    
    # Initialize analyzer
    analyzer = sentiment_analyzer.SentimentAnalyzer(use_transformer=use_transformer)
    
    # Analyze sentiment
    result = analyzer.analyze(comment.processed_text or comment.comment_text)
    
    # Store result in database
    # Check if sentiment already exists
    existing = db.query(SentimentResult).filter(
        SentimentResult.comment_id == comment_id
    ).first()
    
    if existing:
        existing.sentiment_label = result.label
        existing.sentiment_score = result.score
        existing.model_version = result.model_version
        existing.analyzed_at = comment.collected_at or comment.published_at
        db.commit()
        return {
            "message": "Sentiment updated",
            "sentiment": result.label,
            "score": result.score
        }
    else:
        sentiment_result = SentimentResult(
            comment_id=comment_id,
            sentiment_label=result.label,
            sentiment_score=result.score,
            model_version=result.model_version,
            analyzed_at=comment.collected_at or comment.published_at
        )
        
        db.add(sentiment_result)
        db.commit()
        db.refresh(sentiment_result)
        
        return {
            "message": "Sentiment analyzed",
            "sentiment": result.label,
            "score": result.score,
            "sentiment_id": sentiment_result.sentiment_id
        }


@router.post("/analysis/sentiment/bulk/{creator_id}")
async def analyze_sentiment_bulk(
    creator_id: int,
    use_transformer: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze sentiment for every comment belonging to a creator.

    This is what actually populates the sentiment distribution - the
    per-comment endpoint above is only for one comment at a time.
    """
    require_creator_access(db, current_user, creator_id)
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()

    if not comments:
        return {
            "message": "No comments found for this creator",
            "creator_id": creator_id,
            "analyzed": 0,
            "distribution": {}
        }

    analyzer = sentiment_analyzer.SentimentAnalyzer(use_transformer=use_transformer)

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    analyzed = 0

    for comment in comments:
        text = comment.processed_text or comment.comment_text
        if not text:
            continue

        result = analyzer.analyze(text)
        label = result.label if result.label in counts else "neutral"
        counts[label] += 1
        analyzed += 1

        existing = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()

        if existing:
            existing.sentiment_label = result.label
            existing.sentiment_score = result.score
            existing.model_version = result.model_version
            existing.analyzed_at = comment.collected_at or comment.published_at or datetime.utcnow()
        else:
            db.add(SentimentResult(
                comment_id=comment.comment_id,
                sentiment_label=result.label,
                sentiment_score=result.score,
                model_version=result.model_version,
                analyzed_at=comment.collected_at or comment.published_at or datetime.utcnow()
            ))

    db.commit()

    total = max(analyzed, 1)
    return {
        "message": f"Analyzed sentiment for {analyzed} comments",
        "creator_id": creator_id,
        "analyzed": analyzed,
        "distribution": {
            label: {
                "count": count,
                "percentage": round((count / total) * 100, 2),
            }
            for label, count in counts.items()
        },
    }


@router.get("/analysis/sentiment/distribution/{creator_id}")
async def get_sentiment_distribution(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sentiment distribution for a creator's comments.

    Pass ``post_id`` to scope the analysis to a single video.
    """
    from sqlalchemy import func

    require_creator_access(db, current_user, creator_id)
    
    # Get sentiment results joined with comments (comments belong to a post,
    # and posts belong to a creator - so join through Post).
    query = db.query(
        SentimentResult.sentiment_label,
        func.count(SentimentResult.sentiment_id).label('count')
    ).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    results = query.group_by(
        SentimentResult.sentiment_label
    ).all()
    
    total_query = db.query(SentimentResult).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        total_query = total_query.filter(Comment.post_id == post_id)
    total = total_query.count()
    
    distribution = {}
    for label, count in results:
        distribution[label] = {
            "count": count,
            "percentage": round((count / total) * 100, 2) if total > 0 else 0
        }
    
    return {
        "total_comments_analyzed": total,
        "distribution": distribution
    }


# ===== TOPIC MODELLING (FR-05) =====

@router.post("/analysis/topics/{creator_id}")
async def analyze_topics(
    creator_id: int,
    n_topics: int = 5,
    use_bertopic: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform topic modeling on comments."""
    require_creator_access(db, current_user, creator_id)
    # Get all comments for creator
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()
    
    if not comments:
        return {"message": "No comments found for this creator"}
    
    # Extract text for topic modeling
    documents = [comment.processed_text or comment.comment_text for comment in comments]
    
    # Perform topic detection
    detector = topic_modeler.TopicDetector(
        use_bertopic=use_bertopic,
        n_topics=n_topics
    )
    
    result = detector.detect_topics(documents)
    
    # Store topics in database
    # Remove existing topics for this creator to avoid duplicates.
    # NOTE: SQLAlchemy 2.x does not allow .delete() after .join(), so select the
    # matching CommentTopic ids first and delete them by id.
    stale_comment_topic_ids = [
        row[0]
        for row in db.query(CommentTopic.comment_topic_id).join(
            Comment, CommentTopic.comment_id == Comment.comment_id
        ).join(
            Post, Comment.post_id == Post.post_id
        ).filter(
            Post.creator_id == creator_id
        ).all()
    ]
    if stale_comment_topic_ids:
        db.query(CommentTopic).filter(
            CommentTopic.comment_topic_id.in_(stale_comment_topic_ids)
        ).delete(synchronize_session=False)
        db.commit()

    # Store new topics
    topics_data = result.get('topics', [])
    document_dists = result.get('document_distributions', []) or []

    # Map each comment to the topic it is most strongly associated with.
    # Using the real distribution avoids the (comment_id, topic_id) unique
    # constraint being violated by linking every comment to every topic.
    comment_topic_rows = []
    for doc_index, distribution in enumerate(document_dists):
        if doc_index >= len(comments):
            break
        if not distribution:
            continue
        best_topic_index = max(
            range(len(distribution)),
            key=lambda i: distribution[i] if distribution[i] is not None else -1,
        )
        relevance = float(distribution[best_topic_index] or 0.0)
        if relevance <= 0:
            continue
        comment_topic_rows.append((doc_index, best_topic_index, relevance))

    def _topic_name(topic_data: Dict[str, Any], topic_index: int) -> str:
        """Build a readable topic label from its top words."""
        name = topic_data.get("name")
        if name:
            return name
        display_words = topic_data.get("display_words") or []
        if display_words:
            return " ".join(str(w) for w in display_words[:3])
        top_words = topic_data.get("top_words") or []
        words = []
        for entry in top_words[:3]:
            if isinstance(entry, (tuple, list)) and entry:
                words.append(str(entry[0]))
            else:
                words.append(str(entry))
        if not words:
            return f"Topic {topic_index + 1}"
        return " ".join(words)

    for topic_index, topic_data in enumerate(topics_data):
        # Build a stable, unique name. LDA topics have no "name", so derive one
        # from the top words - otherwise every topic collapses into a single
        # row with an empty name.
        display_name = _topic_name(topic_data, topic_index)
        topic_name = display_name.lower().replace(' ', '_')
        display_words = topic_data.get("display_words") or []
        description = (
            "Topic: " + " ".join(str(w) for w in display_words[:5])
            if display_words else f"Topic: {display_name}"
        )

        existing_topic = db.query(Topic).filter(Topic.topic_name == topic_name).first()

        if not existing_topic:
            topic = Topic(
                topic_name=topic_name,
                topic_description=description,
                top_words=json.dumps([str(w) for w in display_words]),
            )
            db.add(topic)
            db.commit()
            db.refresh(topic)
        else:
            topic = existing_topic
            if display_words:
                topic.top_words = json.dumps([str(w) for w in display_words])
                db.commit()

        # Link comments to this topic
        for doc_index, dist_index, relevance in comment_topic_rows:
            if dist_index != topic_index:
                continue
            comment = comments[doc_index]
            already_linked = db.query(CommentTopic).filter(
                CommentTopic.comment_id == comment.comment_id,
                CommentTopic.topic_id == topic.topic_id,
            ).first()
            if already_linked:
                continue
            db.add(CommentTopic(
                comment_id=comment.comment_id,
                topic_id=topic.topic_id,
                relevance_score=relevance,
            ))

    db.commit()

    return {
        "message": "Topic analysis completed",
        "creator_id": creator_id,
        "topics_found": len(topics_data),
        "topics": [
            {
                "topic_id": int(t.get('topic_id', i)),
                "name": _topic_name(t, i),
                "top_words": [
                    [str(w[0]), float(w[1])] if isinstance(w, (tuple, list)) and len(w) > 1 else [str(w), 0.0]
                    for w in (t.get('top_words') or [])[:5]
                ],
                "method": result.get('method', 'unknown')
            }
            for i, t in enumerate(topics_data)
        ]
    }


# ===== AUDIENCE SEGMENTATION (FR-06) =====

@router.post("/analysis/segmentation/{creator_id}")
async def analyze_segmentation(
    creator_id: int,
    n_clusters: int = 5,
    use_dbscan: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform audience segmentation using clustering."""
    require_creator_access(db, current_user, creator_id)
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()
    
    if len(comments) < 2:
        return {"message": "Not enough comments for segmentation"}
    
    import numpy as np
    from services import clustering
    
    # Build real text embeddings with TF-IDF so clusters reflect what the
    # comments actually say (rather than random noise).
    texts = [
        (c.processed_text or c.comment_text or "") for c in comments
    ]
    embeddings = _build_embeddings(texts)
    
    # Perform clustering
    segmenter = clustering.AudienceSegmenter(
        n_clusters=n_clusters,
        use_dbscan=use_dbscan
    )
    
    result = segmenter.segment(embeddings, [c.comment_text for c in comments])
    labels = result.get('labels', [])
    
    # Store segment results in database
    # Remove existing segments for this creator
    db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).delete(synchronize_session=False)
    
    db.query(SegmentComment).delete(synchronize_session=False)
    
    # Create segments
    cluster_sizes = result.get('cluster_sizes', {})
    
    # Name each segment after the keywords most common in that cluster, so the
    # labels reflect what the audience is actually talking about.
    cluster_keywords = result.get('cluster_keywords', {}) or {}
    
    segment_labels = {
        0: "Beginners seeking tutorials",
        1: "Students exploring career opportunities",
        2: "Developers interested in advanced concepts",
        3: "Viewers interested in AI tools",
        4: "People looking for free learning resources"
    }
    
    def _segment_name(cluster_id: int) -> str:
        words = cluster_keywords.get(cluster_id) or cluster_keywords.get(str(cluster_id)) or []
        if words:
            label = " ".join(str(w).title() for w in words[:3])
            return f"{label} viewers"
        return segment_labels.get(cluster_id, f"Segment {cluster_id}")
    
    for cluster_id, size in cluster_sizes.items():
        if int(cluster_id) == -1:
            continue  # Skip noise in DBSCAN
        
        segment = AudienceSegment(
            creator_id=creator_id,
            segment_name=_segment_name(cluster_id),
            segment_description=f"Audience segment with {size} commenters discussing similar topics",
            algorithm_name="K-Means" if not use_dbscan else "DBSCAN",
            created_at=datetime.utcnow()
        )
        db.add(segment)
        db.commit()
        db.refresh(segment)
        
        # Link representative comments to segment
        # Get comments assigned to this cluster
        cluster_comments = [
            c for c, label in zip(comments, labels)
            if int(label) == int(cluster_id)
        ]
        
        for comment in cluster_comments[:5]:  # Top 5 representative comments
            segment_comment = SegmentComment(
                segment_id=segment.segment_id,
                comment_id=comment.comment_id
            )
            db.add(segment_comment)
    
    db.commit()
    
    total_labeled = len(labels) or 1

    segments_payload = []
    segment_lookup = db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).all()

    for segment in segment_lookup:
        member_ids = [
            sc.comment_id
            for sc in db.query(SegmentComment).filter(
                SegmentComment.segment_id == segment.segment_id
            ).all()
        ]
        segments_payload.append({
            "segment_id": segment.segment_id,
            "name": segment.segment_name,
            "description": segment.segment_description,
            "algorithm": segment.algorithm_name,
            "size": len(member_ids),
            "percentage": round((len(member_ids) / total_labeled) * 100, 2),
            "sample_comments": [
                c.comment_text
                for c in comments
                if c.comment_id in member_ids
            ][:3],
        })

    return {
        "message": "Audience segmentation completed",
        "creator_id": creator_id,
        "clusters_formed": len(cluster_sizes),
        "method": "DBSCAN" if use_dbscan else "K-Means",
        "segment_sizes": _json_safe(cluster_sizes),
        "segment_keywords": _json_safe(result.get('cluster_keywords', {})),
        "silhouette_score": _json_safe(result.get('silhouette_score')),
        "segments": segments_payload,
    }


# ===== PAIN POINT DETECTION (FR-07) =====

@router.post("/analysis/pain-points/{creator_id}")
async def detect_pain_points(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Identify recurring complaints and difficulties."""
    from services import pain_points as pain_point_service

    require_creator_access(db, current_user, creator_id)
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()
    
    if not comments:
        return {"message": "No comments found"}
    
    # Build the input for the detector: comment text plus its sentiment.
    comment_rows = []
    for comment in comments:
        sentiment_row = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()
        comment_rows.append({
            "comment_id": comment.comment_id,
            "text": comment.comment_text,
            "processed": comment.processed_text,
            "sentiment": sentiment_row.sentiment_label if sentiment_row else "unanalyzed",
        })
    
    detected = pain_point_service.detect_pain_points(comment_rows)
    
    return {
        "message": "Pain point detection completed",
        "creator_id": creator_id,
        "comments_analyzed": len(comment_rows),
        "pain_points": [
            {
                "type": p["type"],
                "label": p["label"],
                "count": p["count"],
                "share": p["share"],
            }
            for p in detected
        ],
        "top_complaints": [
            {"type": p["type"], "description": p["label"], "count": p["count"]}
            for p in detected[:5]
        ],
    }


@router.post("/analysis/emotions/{creator_id}")
async def analyze_emotions(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Classify comments by emotion: influenced / triggered / hate / love / curious."""
    from services import emotions as emotion_service

    require_creator_access(db, current_user, creator_id)
    query = db.query(Comment).join(Post).filter(Post.creator_id == creator_id)
    if post_id:
        query = query.filter(Comment.post_id == post_id)

    comments = query.all()
    if not comments:
        return {
            "message": "No comments found for this creator",
            "creator_id": creator_id,
            "analysed": 0,
            "distribution": {},
        }

    analyzer = emotion_service.EmotionAnalyzer()
    distribution = {}
    languages = {}

    for comment in comments:
        analysis = analyzer.analyze(comment.comment_text or "")
        comment.emotion_label = analysis["primary"]
        comment.emotion_scores = json.dumps(analysis["scores"])
        comment.emotion_confidence = analysis["confidence"]
        comment.emotion_intensity = analysis["intensity"]
        comment.detected_language = analysis["language"]

        distribution[analysis["primary"]] = distribution.get(analysis["primary"], 0) + 1
        languages[analysis["language"]] = languages.get(analysis["language"], 0) + 1

    db.commit()

    return {
        "message": f"Classified {len(comments)} comments",
        "creator_id": creator_id,
        "post_id": post_id,
        "analysed": len(comments),
        "distribution": distribution,
        "languages": languages,
    }


# ===== CONTENT DEMAND DETECTION (FR-08) =====

@router.post("/analysis/content-requests/{creator_id}")
async def detect_content_requests(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract explicit content requests from comments."""
    require_creator_access(db, current_user, creator_id)
    # Get all comments
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()
    
    if not comments:
        return {"message": "No comments found"}
    
    # Content request patterns based on PRD FR-08
    request_patterns = {
        "tutorial_request": ["tutorial", "please make", "how to", "guide", "walkthrough"],
        "comparison_request": ["compare", "vs", "versus", "difference between"],
        "explanation_request": ["explain", "clarify", "understand", "why", "how does"],
        "updated_content_request": ["updated", "new version", "latest", "current", "recent"],
        "project_walkthrough": ["project", "walkthrough", "build", "create", "example"]
    }
    
    content_requests = []
    
    for comment in comments:
        text = (comment.processed_text or comment.comment_text).lower()
        request_type = None
        requested_topic = None
        confidence = 0.0
        
        # Check each pattern
        for rtype, patterns in request_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    request_type = rtype
                    # Simple confidence based on pattern matches
                    confidence = min(0.5 + (text.count(pattern) * 0.1), 1.0)
                    break
            if request_type:
                break
        
        # Extract requested topic (simple heuristic)
        if request_type:
            # Look for topic keywords after the request pattern
            for word in text.split():
                if word in ['ai', 'python', 'machine', 'learning', 'tutorial', 'code']:
                    requested_topic = word
                    break
        
        if request_type:
            content_requests.append({
                "request_type": request_type,
                "requested_topic": requested_topic or "general content",
                "confidence_score": round(confidence, 2),
                "comment_text": comment.comment_text,
                "comment_id": comment.comment_id
            })
    
    # Remove existing content requests and store new ones
    db.query(ContentRequest).filter(
        ContentRequest.comment_id.in_([c.comment_id for c in comments])
    ).delete(synchronize_session=False)
    
    for req in content_requests:
        request_entity = ContentRequest(
            comment_id=req['comment_id'],
            requested_topic=req['requested_topic'],
            request_category=req['request_type'],
            confidence_score=req['confidence_score']
        )
        db.add(request_entity)
    
    db.commit()
    
    # Group by category
    grouped = {}
    for req in content_requests:
        cat = req['request_type']
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "topic": req['requested_topic'],
            "confidence": req['confidence_score'],
            "comment": req['comment_text'][:100] + "..." if len(req['comment_text']) > 100 else req['comment_text']
        })
    
    return {
        "message": "Content demand detection completed",
        "creator_id": creator_id,
        "total_comments_analyzed": len(comments),
        "content_requests_found": len(content_requests),
        "requests_by_category": grouped,
        "top_requests": [
            {"category": r['request_type'], "topic": r['requested_topic'], "confidence": r['confidence_score']}
            for r in content_requests[:5]
        ]
    }


# ===== ENGAGEMENT ANALYSIS (FR-09) =====

@router.get("/analysis/engagement/{creator_id}")
async def get_engagement_analysis(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze engagement patterns and video comment activity."""
    require_creator_access(db, current_user, creator_id)
    # Get videos and their comment stats
    videos = db.query(Post).filter(Post.creator_id == creator_id).all()
    
    if not videos:
        return {"message": "No videos found for this creator"}
    
    # Get comments per video with sentiment
    from sqlalchemy import func
    
    engagement_data = []
    for video in videos:
        # Total comments
        total_comments = db.query(func.count(Comment.comment_id)).filter(
            Comment.post_id == video.post_id
        ).scalar() or 0
        
        # Comments with sentiment
        commented_videos = db.query(SentimentResult).join(Comment).filter(
            Comment.post_id == video.post_id
        ).count() if total_comments > 0 else 0
        
        # Average like count on comments
        avg_likes = db.query(func.avg(Comment.like_count)).filter(
            Comment.post_id == video.post_id
        ).scalar() or 0
        
        # Sentiment distribution for this video
        sentiment_dist = db.query(
            SentimentResult.sentiment_label,
            func.count(SentimentResult.sentiment_id).label('count')
        ).join(Comment).filter(
            Comment.post_id == video.post_id
        ).group_by(SentimentResult.sentiment_label).all()
        
        sentiment_breakdown = {}
        for label, count in sentiment_dist:
            sentiment_breakdown[label] = count
        
        engagement_data.append({
            "post_id": video.post_id,
            "title": video.title,
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": total_comments,
            "sentiment_analyzed": commented_videos,
            "sentiment_distribution": sentiment_breakdown,
            "avg_comment_likes": round(float(avg_likes), 2)
        })
    
    # Sort by comment activity
    engagement_data.sort(key=lambda x: x['comment_count'], reverse=True)
    
    return {
        "message": "Engagement analysis completed",
        "creator_id": creator_id,
        "total_videos_analyzed": len(videos),
        "engagement_data": engagement_data,
        "most_active_video": engagement_data[0] if engagement_data else None,
        "videos_with_highest_comments": sorted(
            engagement_data, 
            key=lambda x: x['comment_count'], 
            reverse=True
        )[:3]
    }


# ===== HISTORICAL ANALYSIS (FR-10) =====

@router.get("/reports/{creator_id}")
async def get_reports(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get historical reports for a creator."""
    require_creator_access(db, current_user, creator_id)
    reports = db.query(Report).filter(Report.creator_id == creator_id).all()
    
    return {
        "creator_id": creator_id,
        "reports": [
            {
                "report_id": r.report_id,
                "report_name": r.report_name,
                "date_from": r.date_from,
                "date_to": r.date_to,
                "total_comments": r.total_comments,
                "generated_at": r.generated_at
            }
            for r in reports
        ]
    }


@router.post("/reports/generate/{creator_id}")
async def generate_report(
    creator_id: int,
    report_name: str,
    date_from: str,
    date_to: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a new intelligence report."""
    from sqlalchemy import func
    from datetime import datetime, timezone

    require_creator_access(db, current_user, creator_id)

    # Accept ISO dates ("2024-01-01") or full ISO timestamps.
    def _parse_dt(value: str) -> datetime:
        value = (value or "").strip()
        if not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from and date_to must be provided as YYYY-MM-DD",
            )
        try:
            if len(value) == 10:
                return datetime.fromisoformat(value)
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format: {value!r}. Use YYYY-MM-DD.",
            )

    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)
    if dt_to < dt_from:
        dt_from, dt_to = dt_to, dt_from

    # Get comments within date range
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id,
        Post.published_at >= dt_from,
        Post.published_at <= dt_to
    ).all()
    
    total_comments = len(comments)
    
    # Get sentiment distribution
    sentiment_dist = db.query(
        SentimentResult.sentiment_label,
        func.count(SentimentResult.sentiment_id).label('count')
    ).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    ).group_by(SentimentResult.sentiment_label).all()
    
    # Get top topics
    top_topics = db.query(
        Topic.topic_name,
        func.count(CommentTopic.comment_id).label('mentions')
    ).join(CommentTopic).filter(
        CommentTopic.comment_id.in_([c.comment_id for c in comments]),
        Topic.topic_id == CommentTopic.topic_id
    ).group_by(Topic.topic_name).order_by(
        func.count(CommentTopic.comment_id).desc()
    ).limit(5).all()
    
    # Get top content requests
    requests = db.query(ContentRequest.request_category, func.count(ContentRequest.request_id).label('count')) \
        .filter(ContentRequest.comment_id.in_([c.comment_id for c in comments])) \
        .group_by(ContentRequest.request_category).all()
    
    # Generate report
    report = Report(
        creator_id=creator_id,
        report_name=report_name,
        date_from=dt_from,
        date_to=dt_to,
        total_comments=total_comments,
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    return {
        "message": "Report generated successfully",
        "report_id": report.report_id,
        "report_name": report.report_name,
        "date_range": f"{date_from} to {date_to}",
        "total_comments_analyzed": total_comments,
        "summary": {
            "sentiment_distribution": {
                label: count for label, count in sentiment_dist
            },
            "top_topics": [
                {"topic": t.topic_name, "mentions": t.mentions}
                for t in top_topics
            ],
            "content_demand": [
                {"category": r.request_category, "count": r.count}
                for r in requests
            ]
        }
    }


# ===== INTELLIGENCE REPORT (FR-11) =====

@router.get("/intelligence-report/{creator_id}/{report_id}")
async def get_intelligence_report(
    creator_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive intelligence report."""
    from sqlalchemy import func

    require_creator_access(db, current_user, creator_id)
    
    # Get the report
    report = db.query(Report).filter(
        Report.report_id == report_id,
        Report.creator_id == creator_id
    ).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Get date range comments
    comments = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id,
        Post.published_at >= report.date_from,
        Post.published_at <= report.date_to
    ).all()
    
    # Sentiment analysis
    sentiment_labels = [0, 0, 0]  # positive, negative, neutral
    for comment in comments:
        sentiment = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()
        if sentiment:
            if sentiment.sentiment_label == "positive":
                sentiment_labels[0] += 1
            elif sentiment.sentiment_label == "negative":
                sentiment_labels[1] += 1
            else:
                sentiment_labels[2] += 1
    
    # Topic distribution
    topic_dist = db.query(
        Topic.topic_name,
        func.count(CommentTopic.comment_id).label('mentions')
    ).join(CommentTopic).filter(
        CommentTopic.comment_id.in_([c.comment_id for c in comments]),
        Topic.topic_id == CommentTopic.topic_id
    ).group_by(Topic.topic_name).order_by(
        func.count(CommentTopic.comment_id).desc()
    ).limit(10).all()
    
    # Audience segments
    segments = db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).all()
    
    # Pain points
    from services import pain_points as pain_point_service
    pain_rows = []
    for comment in comments:
        sentiment_row = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()
        pain_rows.append({
            "comment_id": comment.comment_id,
            "text": comment.comment_text,
            "processed": comment.processed_text,
            "sentiment": sentiment_row.sentiment_label if sentiment_row else "unanalyzed",
        })
    pain_points = pain_point_service.detect_pain_points(pain_rows)
    
    # Content requests
    requests = db.query(ContentRequest).filter(
        ContentRequest.comment_id.in_([c.comment_id for c in comments])
    ).all()
    
    return {
        "report_id": report.report_id,
        "report_name": report.report_name,
        "date_range": f"{report.date_from} to {report.date_to}",
        "generated_at": report.generated_at,
        "overview": {
            "total_comments": len(comments),
            "positive_percentage": round((sentiment_labels[0] / len(comments)) * 100, 2) if comments else 0,
            "negative_percentage": round((sentiment_labels[1] / len(comments)) * 100, 2) if comments else 0,
            "neutral_percentage": round((sentiment_labels[2] / len(comments)) * 100, 2) if comments else 0
        },
        "sentiment_analysis": {
            "positive": sentiment_labels[0],
            "negative": sentiment_labels[1],
            "neutral": sentiment_labels[2],
            "distribution": {
                "positive": sentiment_labels[0],
                "negative": sentiment_labels[1],
                "neutral": sentiment_labels[2]
            }
        },
        "interest_distribution": [
            {"topic": t.topic_name, "mentions": t.mentions}
            for t in topic_dist
        ],
        "audience_segments": [
            {
                "segment_name": s.segment_name,
                "description": s.segment_description
            }
            for s in segments
        ],
        "pain_points": pain_points.get('pain_points', []) if isinstance(pain_points, dict) else [],
        "content_opportunities": [
            {
                "category": r.request_category,
                "requested_topic": r.requested_topic,
                "confidence": r.confidence_score
            }
            for r in requests
        ]
    }
