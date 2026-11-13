"""Read-side analytics endpoints for the AudienceIQ dashboard.

These complement the action endpoints in ``api.py`` (which mutate data) by
exposing the stored analysis results in the shapes the dashboard needs.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user, require_creator_access, require_post_access
from database import get_db
from models import (
    User, Creator, UserCreator, Post, Commenter, Comment,
    SentimentResult, Topic, CommentTopic, AudienceSegment,
    SegmentComment, ContentRequest, Report, AnalysisRun,
)

router = APIRouter(prefix="/api/v1", tags=["AudienceIQ Insights"])


def _creator_or_404(creator_id: int, db: Session, current_user: User) -> Creator:
    return require_creator_access(db, current_user, creator_id)


def _creator_comments(creator_id: int, db: Session, post_id: Optional[int] = None):
    """All comments belonging to a creator (comments -> posts -> creator).

    Pass ``post_id`` to scope the query to a single video.
    """
    query = db.query(Comment).join(Post).filter(Post.creator_id == creator_id)
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    return query.all()


def _scope(query, post_id: Optional[int] = None):
    """Add a video filter to a query that already joins Comment -> Post."""
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    return query


# ===== CREATOR WORKSPACE =====

@router.get("/creators")
async def list_creators(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List every creator tracked in the workspace, with headline stats."""
    creators = db.query(Creator).join(UserCreator).filter(
        UserCreator.user_id == current_user.user_id
    ).order_by(Creator.creator_id).all()

    payload = []
    for creator in creators:
        posts = db.query(Post).filter(Post.creator_id == creator.creator_id).count()
        comment_count = db.query(Comment).join(Post).filter(
            Post.creator_id == creator.creator_id
        ).count()
        segments = db.query(AudienceSegment).filter(
            AudienceSegment.creator_id == creator.creator_id
        ).count()
        reports = db.query(Report).filter(
            Report.creator_id == creator.creator_id
        ).count()

        payload.append({
            "creator_id": creator.creator_id,
            "name": creator.creator_name,
            "handle": creator.platform_id,
            "platform_type": creator.platform_type,
            "description": creator.description,
            "profile_image": creator.profile_image,
            "created_at": creator.created_at,
            "stats": {
                "videos": posts,
                "comments": comment_count,
                "segments": segments,
                "reports": reports,
            },
        })

    return {"creators": payload, "total": len(payload)}


@router.get("/creators/{creator_id}")
async def get_creator(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single creator's profile and headline stats."""
    creator = _creator_or_404(creator_id, db, current_user)

    posts = db.query(Post).filter(Post.creator_id == creator_id).all()
    total_views = sum(p.view_count or 0 for p in posts)
    total_likes = sum(p.like_count or 0 for p in posts)

    comment_count = db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).count()

    return {
        "creator_id": creator.creator_id,
        "name": creator.creator_name,
        "handle": creator.platform_id,
        "platform_type": creator.platform_type,
        "description": creator.description,
        "profile_image": creator.profile_image,
        "created_at": creator.created_at,
        "stats": {
            "videos": len(posts),
            "comments": comment_count,
            "views": total_views,
            "likes": total_likes,
            "segments": db.query(AudienceSegment).filter(
                AudienceSegment.creator_id == creator_id
            ).count(),
            "reports": db.query(Report).filter(
                Report.creator_id == creator_id
            ).count(),
        },
    }


@router.delete("/creators/{creator_id}")
async def delete_creator(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a creator and all of their analysis data."""
    _creator_or_404(creator_id, db, current_user)

    link_count = db.query(UserCreator).filter(
        UserCreator.creator_id == creator_id
    ).count()
    if link_count > 1:
        db.query(UserCreator).filter(
            UserCreator.creator_id == creator_id,
            UserCreator.user_id == current_user.user_id,
        ).delete(synchronize_session=False)
        db.commit()
        return {"message": "Creator removed from workspace", "creator_id": creator_id}

    post_ids = [p.post_id for p in db.query(Post).filter(
        Post.creator_id == creator_id
    ).all()]
    comment_ids = [c.comment_id for c in db.query(Comment).join(Post).filter(
        Post.creator_id == creator_id
    ).all()]

    if comment_ids:
        db.query(SentimentResult).filter(
            SentimentResult.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        db.query(CommentTopic).filter(
            CommentTopic.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        db.query(SegmentComment).filter(
            SegmentComment.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        db.query(ContentRequest).filter(
            ContentRequest.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
        db.query(Comment).filter(Comment.comment_id.in_(comment_ids)).delete(
            synchronize_session=False
        )

    if post_ids:
        db.query(Post).filter(Post.post_id.in_(post_ids)).delete(
            synchronize_session=False
        )

    db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).delete(synchronize_session=False)
    db.query(Report).filter(Report.creator_id == creator_id).delete(
        synchronize_session=False
    )
    db.query(AnalysisRun).filter(AnalysisRun.creator_id == creator_id).delete(
        synchronize_session=False
    )
    db.query(UserCreator).filter(UserCreator.creator_id == creator_id).delete(
        synchronize_session=False
    )
    db.query(Creator).filter(Creator.creator_id == creator_id).delete(
        synchronize_session=False
    )

    db.commit()
    return {"message": "Creator deleted", "creator_id": creator_id}


# ===== DASHBOARD OVERVIEW =====

@router.get("/dashboard/summary/{creator_id}")
async def dashboard_summary(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything the overview page needs, in a single request."""
    creator = _creator_or_404(creator_id, db, current_user)

    posts = db.query(Post).filter(Post.creator_id == creator_id).all()
    comments = _creator_comments(creator_id, db)

    sentiment_rows = db.query(
        SentimentResult.sentiment_label,
        func.count(SentimentResult.sentiment_id),
    ).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    ).group_by(SentimentResult.sentiment_label).all()

    distribution = {label: count for label, count in sentiment_rows}
    analyzed = sum(distribution.values())
    total = len(comments) or 1

    def pct(count: int) -> float:
        return round((count / total) * 100, 2)

    # Top topics by number of linked comments
    topic_rows = db.query(
        Topic.topic_name,
        func.count(CommentTopic.comment_id),
    ).join(
        CommentTopic, Topic.topic_id == CommentTopic.topic_id
    ).join(
        Comment, CommentTopic.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    ).group_by(Topic.topic_name).order_by(
        func.count(CommentTopic.comment_id).desc()
    ).limit(6).all()

    top_topics = [
        {"topic": (name or "").replace("_", " "), "mentions": mentions}
        for name, mentions in topic_rows
    ]

    # Segments
    segment_rows = db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).all()
    segments = []
    for segment in segment_rows:
        members = db.query(SegmentComment).filter(
            SegmentComment.segment_id == segment.segment_id
        ).count()
        segments.append({
            "segment_id": segment.segment_id,
            "name": segment.segment_name,
            "description": segment.segment_description,
            "algorithm": segment.algorithm_name,
            "size": members,
            "percentage": pct(members),
        })

    # Engagement totals
    total_views = sum(p.view_count or 0 for p in posts)
    total_likes = sum(p.like_count or 0 for p in posts)

    # Most discussed post
    most_discussed = None
    if posts:
        best = max(posts, key=lambda p: len([
            c for c in comments if c.post_id == p.post_id
        ]))
        best_count = len([c for c in comments if c.post_id == best.post_id])
        most_discussed = {
            "post_id": best.post_id,
            "title": best.title,
            "comments": best_count,
            "view_count": best.view_count,
        }

    return {
        "creator": {
            "creator_id": creator.creator_id,
            "name": creator.creator_name,
            "handle": creator.platform_id,
            "platform_type": creator.platform_type,
            "profile_image": creator.profile_image,
        },
        "totals": {
            "videos": len(posts),
            "comments": len(comments),
            "comments_analyzed": analyzed,
            "views": total_views,
            "likes": total_likes,
            "segments": len(segments),
            "topics": len(top_topics),
            "reports": db.query(Report).filter(
                Report.creator_id == creator_id
            ).count(),
        },
        "sentiment": {
            "positive": distribution.get("positive", 0),
            "negative": distribution.get("negative", 0),
            "neutral": distribution.get("neutral", 0),
            "positive_percent": pct(distribution.get("positive", 0)),
            "negative_percent": pct(distribution.get("negative", 0)),
            "neutral_percent": pct(distribution.get("neutral", 0)),
            "analyzed": analyzed,
        },
        "top_topics": top_topics,
        "segments": segments,
        "most_discussed": most_discussed,
    }


# ===== VIDEO & COMMENT LISTS =====

@router.get("/creators/{creator_id}/videos")
async def list_videos(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List a creator's videos with per-video comment and sentiment stats."""
    creator = _creator_or_404(creator_id, db, current_user)
    posts = db.query(Post).filter(
        Post.creator_id == creator_id
    ).order_by(Post.published_at.desc()).all()

    payload = []
    for post in posts:
        comments = db.query(Comment).filter(Comment.post_id == post.post_id).all()
        comment_ids = [c.comment_id for c in comments]

        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        if comment_ids:
            rows = db.query(
                SentimentResult.sentiment_label,
                func.count(SentimentResult.sentiment_id),
            ).filter(
                SentimentResult.comment_id.in_(comment_ids)
            ).group_by(SentimentResult.sentiment_label).all()
            sentiment_counts.update({label: count for label, count in rows})

        payload.append({
            "post_id": post.post_id,
            "title": post.title,
            "description": post.description,
            "published_at": post.published_at,
            "view_count": post.view_count,
            "like_count": post.like_count,
            "comment_count": len(comments),
            "sentiment": sentiment_counts,
        })

    return {"creator_id": creator_id, "videos": payload, "total": len(payload)}


@router.get("/creators/{creator_id}/comments")
async def list_comments(
    creator_id: int,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Browse a creator's comments with sentiment filter and search."""
    creator = _creator_or_404(creator_id, db, current_user)

    query = db.query(Comment).join(Post).filter(Post.creator_id == creator_id)

    if search:
        # Escape LIKE wildcards so a search for "%" cannot pull every row.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Comment.comment_text.ilike(f"%{escaped}%", escape="\\"))

    comments = query.order_by(Comment.collected_at.desc()).all()

    payload = []
    for comment in comments:
        sentiment_row = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()

        if sentiment and sentiment != "all":
            label = sentiment_row.sentiment_label if sentiment_row else "unanalyzed"
            if label != sentiment:
                continue

        payload.append({
            "comment_id": comment.comment_id,
            "post_id": comment.post_id,
            "text": comment.comment_text,
            "like_count": comment.like_count,
            "published_at": comment.published_at,
            "sentiment": sentiment_row.sentiment_label if sentiment_row else "unanalyzed",
            "sentiment_score": sentiment_row.sentiment_score if sentiment_row else None,
        })

    total = len(payload)
    page = payload[offset:offset + limit]

    return {
        "creator_id": creator_id,
        "comments": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


# ===== ANALYSIS READ ENDPOINTS =====

@router.get("/analysis/topics/{creator_id}")
async def list_topics(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stored topics for a creator, ordered by how often they come up."""
    _creator_or_404(creator_id, db, current_user)

    rows = db.query(
        Topic.topic_id,
        Topic.topic_name,
        Topic.topic_description,
        Topic.top_words,
        func.count(CommentTopic.comment_id),
        func.avg(CommentTopic.relevance_score),
    ).join(
        CommentTopic, Topic.topic_id == CommentTopic.topic_id
    ).join(
        Comment, CommentTopic.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        rows = rows.filter(Comment.post_id == post_id)
    rows = rows.group_by(
        Topic.topic_id, Topic.topic_name, Topic.topic_description, Topic.top_words
    ).order_by(
        func.count(CommentTopic.comment_id).desc()
    ).all()

    comment_total = db.query(func.count(Comment.comment_id)).join(Post).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        comment_total = comment_total.filter(Comment.post_id == post_id)
    comment_total = comment_total.scalar() or 1

    topics = []
    for topic_id, name, description, top_words, mentions, avg_relevance in rows:
        try:
            words = json.loads(top_words) if top_words else []
        except (ValueError, TypeError):
            words = []

        # A couple of real comments so the topic is interpretable.
        samples = [
            c.comment_text
            for c in db.query(Comment).join(CommentTopic).filter(
                CommentTopic.topic_id == topic_id
            ).limit(3).all()
        ]

        topics.append({
            "topic_id": topic_id,
            "name": (name or "").replace("_", " "),
            "slug": name,
            "description": description,
            "words": words,
            "mentions": mentions,
            "share": round((mentions / comment_total) * 100, 2),
            "avg_relevance": round(float(avg_relevance or 0), 4),
            "samples": samples,
        })

    return {"creator_id": creator_id, "topics": topics, "total": len(topics)}


@router.get("/analysis/segments/{creator_id}")
async def list_segments(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stored audience segments with representative comments."""
    _creator_or_404(creator_id, db, current_user)

    segments = db.query(AudienceSegment).filter(
        AudienceSegment.creator_id == creator_id
    ).all()

    total_query = db.query(func.count(Comment.comment_id)).join(Post).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        total_query = total_query.filter(Comment.post_id == post_id)
    total_comments = total_query.scalar() or 1

    payload = []
    for segment in segments:
        members = db.query(SegmentComment).filter(
            SegmentComment.segment_id == segment.segment_id
        ).all()
        member_ids = [m.comment_id for m in members]

        samples = []
        if member_ids:
            samples = [
                c.comment_text
                for c in db.query(Comment).filter(
                    Comment.comment_id.in_(member_ids)
                ).all()
            ][:3]

        payload.append({
            "segment_id": segment.segment_id,
            "name": segment.segment_name,
            "description": segment.segment_description,
            "algorithm": segment.algorithm_name,
            "size": len(members),
            "percentage": round((len(members) / total_comments) * 100, 2),
            "sample_comments": samples,
        })

    payload.sort(key=lambda s: s["size"], reverse=True)
    return {"creator_id": creator_id, "segments": payload, "total": len(payload)}


@router.get("/analysis/pain-points/{creator_id}")
async def list_pain_points(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stored pain points with the comments that triggered them."""
    from services import pain_points as pain_point_service

    _creator_or_404(creator_id, db, current_user)

    comments = _creator_comments(creator_id, db, post_id)

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
        "creator_id": creator_id,
        "pain_points": detected,
        "total": len(detected),
    }


@router.get("/analysis/content-requests/{creator_id}")
async def list_content_requests(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stored content demand signals, grouped by category."""
    _creator_or_404(creator_id, db, current_user)

    query = db.query(
        ContentRequest.request_category,
        ContentRequest.requested_topic,
        ContentRequest.confidence_score,
        func.count(ContentRequest.request_id),
    ).join(
        Comment, ContentRequest.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    )
    if post_id:
        query = query.filter(Comment.post_id == post_id)
    rows = query.group_by(
        ContentRequest.request_category,
        ContentRequest.requested_topic,
        ContentRequest.confidence_score,
    ).order_by(
        func.count(ContentRequest.request_id).desc()
    ).all()

    by_category = {}
    items = []
    for category, topic, confidence, count in rows:
        items.append({
            "category": category,
            "topic": topic,
            "confidence": round(float(confidence or 0), 2),
            "count": count,
        })
        by_category.setdefault(category, 0)
        by_category[category] += count

    return {
        "creator_id": creator_id,
        "requests": items,
        "by_category": by_category,
        "total": len(items),
    }


@router.get("/analysis/sentiment/timeseries/{creator_id}")
async def sentiment_timeseries(
    creator_id: int,
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sentiment trend over time, bucketed by day."""
    _creator_or_404(creator_id, db, current_user)

    since = datetime.utcnow() - timedelta(days=days)

    rows = db.query(
        func.date(Comment.collected_at).label("day"),
        SentimentResult.sentiment_label,
        func.count(SentimentResult.sentiment_id),
    ).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id,
        Comment.collected_at >= since,
    ).group_by(
        func.date(Comment.collected_at),
        SentimentResult.sentiment_label,
    ).all()

    buckets = {}
    for day, label, count in rows:
        day_str = str(day)
        bucket = buckets.setdefault(
            day_str, {"date": day_str, "positive": 0, "negative": 0, "neutral": 0}
        )
        bucket[label] = count

    series = sorted(buckets.values(), key=lambda b: b["date"])
    for point in series:
        total = point["positive"] + point["negative"] + point["neutral"]
        point["total"] = total
        point["positive_percent"] = round((point["positive"] / total) * 100, 2) if total else 0
        point["negative_percent"] = round((point["negative"] / total) * 100, 2) if total else 0
        point["neutral_percent"] = round((point["neutral"] / total) * 100, 2) if total else 0

    return {
        "creator_id": creator_id,
        "days": days,
        "series": series,
        "total": len(series),
    }


@router.get("/analysis/emotions/{creator_id}")
async def list_emotions(
    creator_id: int,
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Emotion breakdown: influenced / triggered / hate / love / curious.

    Pass ``post_id`` to scope the analysis to a single video.
    """
    _creator_or_404(creator_id, db, current_user)

    query = db.query(Comment).join(Post).filter(Post.creator_id == creator_id)
    if post_id:
        query = query.filter(Comment.post_id == post_id)

    comments = query.all()
    total = len(comments) or 1

    primary_counts: Dict[str, int] = {}
    label_counts: Dict[str, int] = {}
    language_counts: Dict[str, int] = {}
    examples: Dict[str, List[dict]] = {}

    for comment in comments:
        label = comment.emotion_label or "neutral"
        primary_counts[label] = primary_counts.get(label, 0) + 1

        language_counts[comment.detected_language or "unknown"] = (
            language_counts.get(comment.detected_language or "unknown", 0) + 1
        )

        # Multi-label: a comment can carry several emotions.
        try:
            scores = json.loads(comment.emotion_scores) if comment.emotion_scores else {}
        except (ValueError, TypeError):
            scores = {}

        for emotion in scores:
            label_counts[emotion] = label_counts.get(emotion, 0) + 1

        examples.setdefault(label, []).append({
            "comment_id": comment.comment_id,
            "text": comment.comment_text,
            "author": comment.author_name,
            "likes": comment.like_count,
            "confidence": comment.emotion_confidence,
            "intensity": comment.emotion_intensity,
        })

    # Sort examples by how strongly they scored.
    for label, rows in examples.items():
        rows.sort(key=lambda r: (r.get("confidence") or 0, r.get("likes") or 0), reverse=True)
        examples[label] = rows[:5]

    analysed = sum(1 for c in comments if c.emotion_label)

    return {
        "creator_id": creator_id,
        "post_id": post_id,
        "total_comments": len(comments),
        "analysed": analysed,
        "primary": [
            {
                "emotion": label,
                "count": count,
                "percentage": round((count / total) * 100, 2),
            }
            for label, count in sorted(primary_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "multi_label": [
            {
                "emotion": label,
                "count": count,
                "percentage": round((count / total) * 100, 2),
            }
            for label, count in sorted(label_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "languages": [
            {"language": lang, "count": count}
            for lang, count in sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "examples": examples,
    }


@router.get("/videos/{post_id}/emotions")
async def video_emotions(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Emotion breakdown for one video."""
    post = require_post_access(db, current_user, post_id)
    return await list_emotions(
        post.creator_id,
        post_id=post_id,
        db=db,
        current_user=current_user,
    )


@router.get("/analysis/overview/{creator_id}")
async def analysis_overview(
    creator_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Counts of what analysis data exists, so the UI can prompt the user."""
    _creator_or_404(creator_id, db, current_user)

    comments = db.query(func.count(Comment.comment_id)).join(Post).filter(
        Post.creator_id == creator_id
    ).scalar() or 0

    sentiment = db.query(func.count(SentimentResult.sentiment_id)).join(
        Comment, SentimentResult.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    ).scalar() or 0

    topics = db.query(func.count(func.distinct(CommentTopic.topic_id))).join(
        Comment, CommentTopic.comment_id == Comment.comment_id
    ).join(
        Post, Comment.post_id == Post.post_id
    ).filter(
        Post.creator_id == creator_id
    ).scalar() or 0

    segments = db.query(func.count(AudienceSegment.segment_id)).filter(
        AudienceSegment.creator_id == creator_id
    ).scalar() or 0

    return {
        "creator_id": creator_id,
        "comments": comments,
        "sentiment_analyzed": sentiment,
        "topics": topics,
        "segments": segments,
        "needs_sentiment": comments > 0 and sentiment == 0,
        "needs_topics": comments > 0 and topics == 0,
        "needs_segmentation": comments > 1 and segments == 0,
    }
