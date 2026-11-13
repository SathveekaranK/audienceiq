from database import Base
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean, Text, 
    ForeignKey, Table, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime


# ... (rest of the models would import Base from database)
# But since we're defining them in the same file flow, let's keep Base reference
# Actually, the models.py already has Base references - let me ensure consistency

# The models import Base from database.py at the top
# But since we're creating files sequentially, let me just define the models properly
# Here's the corrected approach - Base is imported from database

# Since this file references Base, and database.py creates it, the import order matters.
# For now, let's define the models assuming Base will be available from database module.

# If running into circular import issues, we can use deferred Base = declarative_base() pattern.


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user_creators = relationship("UserCreator", back_populates="user")
    
    __table_args__ = (
        Index('ix_users_username', 'username'),
        Index('ix_users_email', 'email'),
    )


class Creator(Base):
    __tablename__ = "creators"
    
    creator_id = Column(Integer, primary_key=True, index=True)
    platform_id = Column(String(100), nullable=False, index=True)
    platform_type = Column(String(20), nullable=False, default="youtube")
    creator_name = Column(String(200), nullable=False)
    description = Column(Text)
    profile_image = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = relationship("Post", back_populates="creator")
    analysis_runs = relationship("AnalysisRun", back_populates="creator")
    user_creators = relationship("UserCreator", back_populates="creator")
    audience_segments = relationship("AudienceSegment", back_populates="creator")
    reports = relationship("Report", back_populates="creator")
    
    __table_args__ = (
        Index('ix_creators_name', 'creator_name'),
    )


class UserCreator(Base):
    __tablename__ = "user_creators"
    
    user_creator_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="user_creators")
    creator = relationship("Creator", back_populates="user_creators")


class Post(Base):
    __tablename__ = "posts"
    
    post_id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    platform_post_id = Column(String(200), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    published_at = Column(DateTime)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    # Extra detail pulled from YouTube when a real video is analysed.
    duration_seconds = Column(Integer)
    thumbnail_url = Column(String(500))
    watch_url = Column(String(300))
    source_url = Column(String(300))
    
    # Relationships
    creator = relationship("Creator", back_populates="posts")
    comments = relationship("Comment", back_populates="post")
    
    __table_args__ = (
        Index('ix_posts_creator_id', 'creator_id'),
        Index('ix_posts_platform_post_id', 'platform_post_id'),
    )


class Commenter(Base):
    __tablename__ = "commenters"
    
    commenter_id = Column(Integer, primary_key=True, index=True)
    platform_commenter_id = Column(String(200), nullable=False, unique=True)
    display_name = Column(String(200))
    
    # Relationships
    comments = relationship("Comment", back_populates="commenter")
    
    __table_args__ = (
        Index('ix_commenters_platform_id', 'platform_commenter_id'),
    )


class Comment(Base):
    __tablename__ = "comments"
    
    comment_id = Column(Integer, primary_key=True, index=True)
    platform_comment_id = Column(String(200), nullable=False, unique=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False)
    commenter_id = Column(Integer, ForeignKey("commenters.commenter_id"), nullable=True)
    parent_comment_id = Column(Integer, ForeignKey("comments.comment_id"), nullable=True)
    comment_text = Column(Text, nullable=False)
    processed_text = Column(Text)  # NLP-cleaned text, set during collection/analysis
    like_count = Column(Integer, default=0)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Who left the comment (when it came from YouTube).
    author_name = Column(String(150))
    is_pinned = Column(Boolean, default=False)

    # Emotion classification (influenced / triggered / hate / love / curious).
    emotion_label = Column(String(20), index=True)
    emotion_scores = Column(Text)  # JSON map of emotion -> score
    emotion_confidence = Column(Float)
    emotion_intensity = Column(Float)
    detected_language = Column(String(20))
    
    # Relationships
    post = relationship("Post", back_populates="comments")
    commenter = relationship("Commenter", back_populates="comments")
    parent_comment = relationship("Comment", remote_side=[comment_id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent_comment")
    sentiment_result = relationship("SentimentResult", back_populates="comment", uselist=False)
    comment_topics = relationship("CommentTopic", back_populates="comment")
    segment_comments = relationship("SegmentComment", back_populates="comment")
    content_requests = relationship("ContentRequest", back_populates="comment")
    
    __table_args__ = (
        Index('ix_comments_post_id', 'post_id'),
        Index('ix_comments_published_at', 'published_at'),
        Index('ix_comments_collected_at', 'collected_at'),
    )


class SentimentResult(Base):
    __tablename__ = "sentiment_results"
    
    sentiment_id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.comment_id"), nullable=False, unique=True)
    sentiment_label = Column(String(20), nullable=False)  # positive, negative, neutral
    sentiment_score = Column(Float, nullable=False)  # -1 to 1 or 0 to 1
    model_version = Column(String(50), nullable=False, default="v1.0")
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    comment = relationship("Comment", back_populates="sentiment_result")
    
    __table_args__ = (
        Index('ix_sentiment_comment_id', 'comment_id'),
    )


class Topic(Base):
    __tablename__ = "topics"
    
    topic_id = Column(Integer, primary_key=True, index=True)
    topic_name = Column(String(200), nullable=False, unique=True)
    topic_description = Column(Text)
    top_words = Column(Text)  # JSON list of the words that define this topic
    
    # Relationships
    comment_topics = relationship("CommentTopic", back_populates="topic")
    
    __table_args__ = (
        Index('ix_topics_name', 'topic_name'),
    )


class CommentTopic(Base):
    __tablename__ = "comment_topics"
    
    comment_topic_id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.comment_id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.topic_id"), nullable=False)
    relevance_score = Column(Float, nullable=False, default=1.0)
    
    # Relationships
    comment = relationship("Comment", back_populates="comment_topics")
    topic = relationship("Topic", back_populates="comment_topics")
    
    __table_args__ = (
        Index('ix_comment_topics_comment_id', 'comment_id'),
        Index('ix_comment_topics_topic_id', 'topic_id'),
        UniqueConstraint('comment_id', 'topic_id', name='uq_comment_topic'),
    )


class AudienceSegment(Base):
    __tablename__ = "audience_segments"
    
    segment_id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    segment_name = Column(String(200), nullable=False)
    segment_description = Column(Text)
    algorithm_name = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = relationship("Creator", back_populates="audience_segments")
    segment_comments = relationship("SegmentComment", back_populates="segment")
    
    __table_args__ = (
        Index('ix_segments_creator_id', 'creator_id'),
        Index('ix_segments_name', 'segment_name'),
    )


class SegmentComment(Base):
    __tablename__ = "segment_comments"
    
    segment_comment_id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("audience_segments.segment_id"), nullable=False)
    comment_id = Column(Integer, ForeignKey("comments.comment_id"), nullable=False)
    
    # Relationships
    segment = relationship("AudienceSegment", back_populates="segment_comments")
    comment = relationship("Comment", back_populates="segment_comments")
    
    __table_args__ = (
        Index('ix_segment_comments_segment_id', 'segment_id'),
        Index('ix_segment_comments_comment_id', 'comment_id'),
        UniqueConstraint('segment_id', 'comment_id', name='uq_segment_comment'),
    )


class ContentRequest(Base):
    __tablename__ = "content_requests"
    
    request_id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.comment_id"), nullable=False)
    requested_topic = Column(String(200), nullable=False)
    request_category = Column(String(100), nullable=False)  # tutorial, comparison, explanation, etc.
    confidence_score = Column(Float, nullable=False, default=1.0)
    
    # Relationships
    comment = relationship("Comment", back_populates="content_requests")
    
    __table_args__ = (
        Index('ix_content_requests_comment_id', 'comment_id'),
    )


class Report(Base):
    __tablename__ = "reports"
    
    report_id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    report_name = Column(String(200), nullable=False)
    date_from = Column(DateTime)
    date_to = Column(DateTime)
    total_comments = Column(Integer, default=0)
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = relationship("Creator", back_populates="reports")
    
    __table_args__ = (
        Index('ix_reports_creator_id', 'creator_id'),
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    
    analysis_id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("creators.creator_id"), nullable=False)
    model_version = Column(String(50), nullable=False, default="v1.0")
    analysis_status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    comments_processed = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    creator = relationship("Creator", back_populates="analysis_runs")
    
    __table_args__ = (
        Index('ix_analysis_runs_creator_id', 'creator_id'),
        Index('ix_analysis_runs_status', 'analysis_status'),
    )