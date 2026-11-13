"""Video-first analysis endpoints.

Instead of tracking a whole channel, you can point AudienceIQ at a single
YouTube video. The video's real comments are fetched straight from YouTube,
stored against the channel, and then analysed like any other content.

Endpoints
---------
``POST /api/v1/videos/resolve``      - preview a video without saving anything
``POST /api/v1/videos/analyze``      - fetch comments + run the full analysis
``GET  /api/v1/videos/workspace``    - every video that has been analysed
"""

from datetime import datetime, timezone
from typing import List, Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_post_access
from database import get_db
from models import (
    Creator, Post, Comment, UserCreator, User,
    SentimentResult, CommentTopic, AudienceSegment, SegmentComment,
    ContentRequest, Report, Topic,
)

router = APIRouter(prefix="/api/v1", tags=["AudienceIQ Videos"])


def _youtube_client():
    from services.youtube import YouTubeClient
    return YouTubeClient()


def _parse_published(value: str) -> Optional[datetime]:
    """Turn YouTube's ISO timestamp into a naive UTC datetime."""
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (ValueError, TypeError):
        return None


def _get_or_create_creator(db: Session, meta: dict) -> Creator:
    """Find the channel this video belongs to, creating it if needed."""
    channel_id = meta.get("channel_id") or meta.get("platform_id") or meta["video_id"]

    creator = db.query(Creator).filter(
        Creator.platform_id == channel_id
    ).first()
    if not creator:
        creator = Creator(
            creator_name=meta.get("channel") or "Unknown channel",
            platform_type="youtube",
            platform_id=channel_id,
            description=meta.get("description", "")[:500] or None,
        )
        db.add(creator)
        db.commit()
        db.refresh(creator)
    return creator


def _get_or_create_post(db: Session, creator: Creator, meta: dict) -> Post:
    """Find the video, creating it if needed."""
    post = db.query(Post).filter(
        Post.platform_post_id == meta["video_id"]
    ).first()

    if not post:
        post = Post(
            creator_id=creator.creator_id,
            platform_post_id=meta["video_id"],
            title=meta.get("title") or meta["video_id"],
            description=(meta.get("description") or "")[:2000] or None,
            published_at=_parse_published(meta.get("published_at") or ""),
            view_count=meta.get("view_count") or 0,
            like_count=meta.get("like_count") or 0,
            duration_seconds=meta.get("duration_seconds"),
            thumbnail_url=meta.get("thumbnail_url"),
            watch_url=f"https://www.youtube.com/watch?v={meta['video_id']}",
            source_url=meta.get("source_url"),
        )
        db.add(post)
        db.commit()
        db.refresh(post)
    else:
        # Refresh the stats so repeated runs show current numbers.
        post.view_count = meta.get("view_count") or post.view_count
        if meta.get("like_count"):
            post.like_count = meta["like_count"]
        if meta.get("thumbnail_url"):
            post.thumbnail_url = meta["thumbnail_url"]
        db.commit()

    return post


def _link_to_user(db: Session, creator: Creator, user: User) -> None:
    """Attach the channel to the authenticated user's workspace."""
    if not db.query(UserCreator).filter(
        UserCreator.user_id == user.user_id,
        UserCreator.creator_id == creator.creator_id,
    ).first():
        db.add(UserCreator(user_id=user.user_id, creator_id=creator.creator_id))
        db.commit()


@router.post("/videos/resolve")
async def resolve_video(
    url: str,
    current_user: User = Depends(get_current_user),
):
    """Look up a YouTube video without saving anything.

    Used by the UI to show a preview card before the user commits to
    pulling in the comments.
    """
    client = _youtube_client()
    try:
        meta = client.resolve(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    meta["watch_url"] = f"https://www.youtube.com/watch?v={meta['video_id']}"
    return meta


@router.post("/videos/analyze")
async def analyze_video(
    url: str,
    max_comments: int = Query(120, ge=1, le=500),
    run_analysis: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a YouTube video's comments and analyse them.

    This is the main entry point for video-first analysis. It:

    1. resolves the video metadata,
    2. creates the channel and video if they are new,
    3. downloads the real comments,
    4. optionally runs sentiment, topic, segmentation, pain point,
       content demand and emotion analysis on them.
    """
    from services import (
        text_preprocessor, sentiment_analyzer, topic_modeler, clustering,
        pain_points as pain_point_service, emotions as emotion_service,
    )
    from services.youtube import YouTubeError

    client = _youtube_client()

    try:
        meta = client.resolve(url)
    except YouTubeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach YouTube: {exc}",
        ) from exc

    meta["source_url"] = url
    creator = _get_or_create_creator(db, meta)
    _link_to_user(db, creator, current_user)
    post = _get_or_create_post(db, creator, meta)

    # ---- fetch the real comments -------------------------------------
    try:
        fetched = client.fetch_comments(meta["video_id"], max_comments=max_comments)
    except YouTubeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch comments: {exc}",
        ) from exc

    existing_ids = {
        c.platform_comment_id
        for c in db.query(Comment).filter(Comment.post_id == post.post_id).all()
    }

    added = 0
    for comment in fetched:
        platform_id = f"yt_{comment['comment_id']}"
        if platform_id in existing_ids:
            continue
        processed = text_preprocessor.preprocess_comment(comment.get("text") or "")
        db.add(Comment(
            platform_comment_id=platform_id,
            post_id=post.post_id,
            comment_text=comment.get("text") or "",
            processed_text=processed,
            like_count=comment.get("likes") or 0,
            published_at=_parse_published(comment.get("published_at") or ""),
            collected_at=datetime.utcnow(),
            author_name=(comment.get("author") or None),
            is_pinned=bool(comment.get("is_pinned")),
        ))
        added += 1

    db.commit()

    # Keep the stored count in sync with reality.
    post.comment_count = db.query(Comment).filter(
        Comment.post_id == post.post_id
    ).count()
    db.commit()

    # ---- run the analysis --------------------------------------------
    results = {}
    if run_analysis:
        results = _analyse_video(
            db, creator, post, analyzer_bundle={
                "sentiment": sentiment_analyzer,
                "topic_modeler": topic_modeler,
                "clustering": clustering,
                "pain_points": pain_point_service,
                "emotions": emotion_service,
            },
        )

    return {
        "message": "Video analysed",
        "creator": {
            "creator_id": creator.creator_id,
            "name": creator.creator_name,
            "handle": creator.platform_id,
        },
        "video": {
            "post_id": post.post_id,
            "video_id": meta["video_id"],
            "title": post.title,
            "channel": meta.get("channel"),
            "watch_url": post.watch_url,
            "thumbnail_url": post.thumbnail_url,
            "view_count": post.view_count,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "duration_seconds": post.duration_seconds,
        },
        "comments_fetched": len(fetched),
        "comments_added": added,
        "analysis": results,
    }


def _analyse_video(db: Session, creator: Creator, post: Post, analyzer_bundle: dict) -> dict:
    """Run every analysis over a single video's comments."""
    from services import text_preprocessor

    sentiment_analyzer = analyzer_bundle["sentiment"]
    topic_modeler = analyzer_bundle["topic_modeler"]
    clustering = analyzer_bundle["clustering"]
    pain_point_service = analyzer_bundle["pain_points"]
    emotion_service = analyzer_bundle["emotions"]

    comments = db.query(Comment).filter(Comment.post_id == post.post_id).all()
    if not comments:
        return {"message": "No comments to analyse"}

    results = {}

    # -- sentiment ------------------------------------------------------
    analyzer = sentiment_analyzer.SentimentAnalyzer()
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for comment in comments:
        text = comment.processed_text or comment.comment_text
        if not text:
            continue
        result = analyzer.analyze(text)

        existing = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()
        if existing:
            existing.sentiment_label = result.label
            existing.sentiment_score = result.score
            existing.model_version = result.model_version
        else:
            db.add(SentimentResult(
                comment_id=comment.comment_id,
                sentiment_label=result.label,
                sentiment_score=result.score,
                model_version=result.model_version,
                analyzed_at=datetime.utcnow(),
            ))
        counts[result.label if result.label in counts else "neutral"] += 1
    db.commit()
    results["sentiment"] = counts

    # -- emotions -------------------------------------------------------
    emotion_analyzer = emotion_service.EmotionAnalyzer()
    emotion_counts = {}
    for comment in comments:
        analysis = emotion_analyzer.analyze(comment.comment_text or "")
        comment.emotion_label = analysis["primary"]
        comment.emotion_scores = json.dumps(analysis["scores"])
        comment.emotion_confidence = analysis["confidence"]
        comment.emotion_intensity = analysis["intensity"]
        comment.detected_language = analysis["language"]
        emotion_counts[analysis["primary"]] = emotion_counts.get(analysis["primary"], 0) + 1
    db.commit()
    results["emotions"] = emotion_counts

    # -- topics ---------------------------------------------------------
    documents = [c.processed_text or c.comment_text for c in comments]
    try:
        detector = topic_modeler.TopicDetector()
        topic_result = detector.detect_topics(documents)
        topics = topic_result.get("topics", [])
        distributions = topic_result.get("document_distributions") or []

        # Store one topic per comment, using the strongest signal.
        for index, comment in enumerate(comments):
            if index >= len(distributions):
                break
            distribution = distributions[index]
            if not distribution:
                continue
            best = max(range(len(distribution)), key=lambda i: distribution[i] or 0)
            if (distribution[best] or 0) <= 0:
                continue

            # Topic names come from the words people actually used.
            topic_info = topics[best] if best < len(topics) else {}
            words = topic_info.get("display_words") or []
            name = "_".join(str(w).lower() for w in words[:3]) or f"topic_{best + 1}"

            topic = db.query(Topic).filter(Topic.topic_name == name).first()
            if not topic:
                topic = Topic(
                    topic_name=name,
                    topic_description="Topic: "
                    + (" ".join(str(w) for w in words[:3]) or name),
                    top_words=json.dumps([str(w) for w in words]),
                )
                db.add(topic)
                db.commit()
                db.refresh(topic)
            else:
                topic.top_words = json.dumps([str(w) for w in words])
                db.commit()
            if not db.query(CommentTopic).filter(
                CommentTopic.comment_id == comment.comment_id,
                CommentTopic.topic_id == topic.topic_id,
            ).first():
                db.add(CommentTopic(
                    comment_id=comment.comment_id,
                    topic_id=topic.topic_id,
                    relevance_score=float(distribution[best] or 0),
                ))
        db.commit()
        results["topics"] = len(topics)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Topic analysis failed")
        results["topics_error"] = "Topic analysis failed - see the server log."

    # -- pain points ----------------------------------------------------
    rows = []
    for comment in comments:
        sentiment_row = db.query(SentimentResult).filter(
            SentimentResult.comment_id == comment.comment_id
        ).first()
        rows.append({
            "comment_id": comment.comment_id,
            "text": comment.comment_text,
            "processed": comment.processed_text,
            "sentiment": sentiment_row.sentiment_label if sentiment_row else "unanalyzed",
        })
    detected = pain_point_service.detect_pain_points(rows)
    results["pain_points"] = len(detected)

    # -- content demand -------------------------------------------------
    try:
        from services.content_demand import ContentDemandDetector
        detector = ContentDemandDetector()
        demand = detector.detect_requests([c.comment_text for c in comments])
        results["content_requests"] = demand["total"]
    except Exception as exc:  # noqa: BLE001
        results["content_requests_error"] = str(exc)

    return results


@router.post("/videos/{post_id}/analyze")
async def analyze_existing_video(
    post_id: int,
    max_comments: int = Query(120, ge=1, le=500),
    run_analysis: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-fetch the comments for a video that is already tracked and re-run
    the analysis on them."""
    from services.youtube import YouTubeError, YouTubeClient

    post = require_post_access(db, current_user, post_id)

    creator = db.query(Creator).filter(
        Creator.creator_id == post.creator_id
    ).first()

    client = YouTubeClient()
    try:
        meta = client.resolve(post.platform_post_id)
        fetched = client.fetch_comments(meta["video_id"], max_comments=max_comments)
    except YouTubeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    existing_ids = {
        c.platform_comment_id
        for c in db.query(Comment).filter(Comment.post_id == post.post_id).all()
    }

    from services import text_preprocessor
    added = 0
    for comment in fetched:
        platform_id = f"yt_{comment['comment_id']}"
        if platform_id in existing_ids:
            continue
        db.add(Comment(
            platform_comment_id=platform_id,
            post_id=post.post_id,
            comment_text=comment.get("text") or "",
            processed_text=text_preprocessor.preprocess_comment(comment.get("text") or ""),
            like_count=comment.get("likes") or 0,
            published_at=_parse_published(comment.get("published_at") or ""),
            collected_at=datetime.utcnow(),
            author_name=(comment.get("author") or None),
            is_pinned=bool(comment.get("is_pinned")),
        ))
        added += 1
    db.commit()

    post.comment_count = db.query(Comment).filter(
        Comment.post_id == post.post_id
    ).count()
    db.commit()

    results = {}
    if run_analysis and creator:
        from services import (
            sentiment_analyzer, topic_modeler, clustering,
            pain_points as pain_point_service, emotions as emotion_service,
        )
        results = _analyse_video(
            db, creator, post, analyzer_bundle={
                "sentiment": sentiment_analyzer,
                "topic_modeler": topic_modeler,
                "clustering": clustering,
                "pain_points": pain_point_service,
                "emotions": emotion_service,
            },
        )

    return {
        "message": "Video re-analysed",
        "post_id": post.post_id,
        "comments_fetched": len(fetched),
        "comments_added": added,
        "analysis": results,
    }


@router.get("/videos/workspace")
async def video_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every video that has been analysed, with its headline numbers."""
    posts = db.query(Post).join(
        UserCreator, UserCreator.creator_id == Post.creator_id
    ).filter(
        UserCreator.user_id == current_user.user_id
    ).order_by(Post.published_at.desc()).all()

    payload = []
    for post in posts:
        creator = db.query(Creator).filter(
            Creator.creator_id == post.creator_id
        ).first()

        sentiment_rows = db.query(
            SentimentResult.sentiment_label,
        ).join(
            Comment, SentimentResult.comment_id == Comment.comment_id
        ).filter(
            Comment.post_id == post.post_id
        ).all()
        sentiment_counts = {}
        for (label,) in sentiment_rows:
            sentiment_counts[label] = sentiment_counts.get(label, 0) + 1

        emotion_rows = db.query(
            Comment.emotion_label,
        ).filter(
            Comment.post_id == post.post_id
        ).all()
        emotion_counts = {}
        for (label,) in emotion_rows:
            if label:
                emotion_counts[label] = emotion_counts.get(label, 0) + 1

        payload.append({
            "post_id": post.post_id,
            "creator_id": post.creator_id,
            "channel": creator.creator_name if creator else "Unknown",
            "title": post.title,
            "thumbnail_url": post.thumbnail_url,
            "watch_url": post.watch_url,
            "view_count": post.view_count,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "duration_seconds": post.duration_seconds,
            "sentiment": sentiment_counts,
            "emotions": emotion_counts,
        })

    return {"videos": payload, "total": len(payload)}
