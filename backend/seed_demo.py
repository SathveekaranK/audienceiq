"""Seed the database with a demo channel, videos and comments.

Run it from the backend folder:

    python seed_demo.py

It is safe to run multiple times - existing rows are reused rather than
duplicated. Use ``--reset`` to wipe the demo data first.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from database import SessionLocal, init_db  # noqa: E402
from models import User, Creator, UserCreator, Post, Comment  # noqa: E402

DEMO_USER = {
    "username": "demo",
    "email": "demo@audienceiq.local",
    "password_hash": "demo-not-a-real-hash",
}

DEMO_CHANNEL = {
    "platform_id": "yt_techtalksdaily",
    "creator_name": "TechTalks Daily",
    "platform_type": "youtube",
    "description": "Beginner friendly AI and programming tutorials.",
}

DEMO_VIDEOS = [
    {
        "platform_post_id": "yt_techtalksdaily_v1",
        "title": "Getting Started with AI",
        "description": "A beginner friendly introduction to machine learning.",
        "views": 48200,
        "likes": 3120,
        "days_ago": 45,
    },
    {
        "platform_post_id": "yt_techtalksdaily_v2",
        "title": "Your First Python Project",
        "description": "Build a working script from scratch.",
        "views": 31500,
        "likes": 1890,
        "days_ago": 28,
    },
    {
        "platform_post_id": "yt_techtalksdaily_v3",
        "title": "Prompt Engineering in 2024",
        "description": "Practical techniques for better AI prompts.",
        "views": 62900,
        "likes": 4870,
        "days_ago": 12,
    },
]

# (video key, text, likes, days_ago)
DEMO_COMMENTS = [
    ("v1", "This is great! I finally understand how it works, thanks for the clear explanation.", 42, 44),
    ("v1", "Very helpful tutorial, the pacing is perfect and the examples are easy to follow.", 38, 44),
    ("v1", "Excellent content! I've been waiting for a beginner friendly guide like this.", 31, 43),
    ("v1", "Love how practical this is. I built my first project following along.", 27, 42),
    ("v1", "Great video, but some parts go too fast and I had to rewind a few times.", 19, 41),
    ("v1", "Really good overview, though it would help to see more hands-on demonstrations.", 16, 40),
    ("v1", "Thanks, this answered a lot of my questions about the topic.", 12, 39),
    ("v1", "The explanation is clear but it assumes you already know some programming.", 14, 38),
    ("v1", "Super helpful, I shared this with my whole team and we all learned a lot.", 9, 37),
    ("v1", "Good content overall. Please make a follow up on the advanced techniques.", 7, 36),
    ("v1", "Fantastic, this is exactly the kind of tutorial I was looking for.", 11, 35),
    ("v1", "Solid video, but could you include the downloadable resources in the description?", 8, 34),
    ("v1", "Could you make a follow-up video?", 5, 33),
    ("v1", "I wish there were more practical demonstrations.", 6, 32),
    ("v1", "Awesome content, subscribed!", 4, 31),
    ("v2", "Finally a tutorial that does not skip the boring parts. Thank you!", 22, 27),
    ("v2", "The explanation was too fast, hard to follow.", 13, 26),
    ("v2", "Can you explain how decorators work in more detail?", 10, 25),
    ("v2", "How do I deploy this to the cloud once I finish it?", 9, 24),
    ("v2", "Please make a series on testing, this would help a lot.", 8, 23),
    ("v2", "Really helpful, I understand the basics now.", 7, 22),
    ("v3", "Prompt engineering tips like this are gold. Saving this video.", 51, 11),
    ("v3", "I have been using these prompts and my results are way better now.", 33, 10),
    ("v3", "Would love a follow up on prompt chaining for longer workflows.", 24, 9),
    ("v3", "The examples are great but the theory section was too long.", 18, 8),
    ("v3", "Can you show how to use this with the API?", 15, 7),
    ("v3", "This cleared up so much confusion for me, thanks!", 12, 6),
    ("v3", "Please make a video about RAG systems next.", 9, 5),
]


def seed(reset: bool = False) -> None:
    init_db()
    db = SessionLocal()

    try:
        existing_demo = db.query(Creator).filter(
            Creator.platform_id == DEMO_CHANNEL["platform_id"]
        ).first()

        # Nothing to do when the demo channel is already seeded.
        if existing_demo and not reset:
            comment_count = db.query(Comment).join(Post).filter(
                Post.creator_id == existing_demo.creator_id
            ).count()
            if comment_count > 0:
                print(
                    f"[seed] Demo data already present "
                    f"({comment_count} comments). Use --reset to rebuild it."
                )
                return

        if reset:
            print("[seed] Removing existing demo data...")
            if existing_demo:
                post_ids = [
                    p.post_id
                    for p in db.query(Post).filter(
                        Post.creator_id == existing_demo.creator_id
                    ).all()
                ]
                comment_ids = [
                    c.comment_id
                    for c in db.query(Comment).filter(
                        Comment.post_id.in_(post_ids)
                    ).all()
                ] if post_ids else []
                if comment_ids:
                    db.query(Comment).filter(
                        Comment.comment_id.in_(comment_ids)
                    ).delete(synchronize_session=False)
                if post_ids:
                    db.query(Post).filter(Post.post_id.in_(post_ids)).delete(
                        synchronize_session=False
                    )
                db.query(UserCreator).filter(
                    UserCreator.creator_id == existing_demo.creator_id
                ).delete(synchronize_session=False)
                db.query(Creator).filter(
                    Creator.creator_id == existing_demo.creator_id
                ).delete(synchronize_session=False)
                db.commit()

        # User
        user = db.query(User).filter(
            User.username == DEMO_USER["username"]
        ).first()
        if not user:
            user = User(**DEMO_USER)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Creator
        creator = db.query(Creator).filter(
            Creator.platform_id == DEMO_CHANNEL["platform_id"]
        ).first()
        if not creator:
            creator = Creator(**DEMO_CHANNEL)
            db.add(creator)
            db.commit()
            db.refresh(creator)

        if not db.query(UserCreator).filter(
            UserCreator.user_id == user.user_id,
            UserCreator.creator_id == creator.creator_id,
        ).first():
            db.add(UserCreator(user_id=user.user_id, creator_id=creator.creator_id))
            db.commit()

        # Videos
        posts = {}
        for spec in DEMO_VIDEOS:
            post = db.query(Post).filter(
                Post.platform_post_id == spec["platform_post_id"]
            ).first()
            if not post:
                post = Post(
                    creator_id=creator.creator_id,
                    platform_post_id=spec["platform_post_id"],
                    title=spec["title"],
                    description=spec["description"],
                    published_at=datetime.utcnow()
                    - timedelta(days=spec["days_ago"]),
                    view_count=spec["views"],
                    like_count=spec["likes"],
                    comment_count=0,
                )
                db.add(post)
                db.commit()
                db.refresh(post)
            posts[spec["platform_post_id"].rsplit("_", 1)[-1]] = post

        # Comments
        existing_ids = {c.platform_comment_id for c in db.query(Comment).all()}
        added = 0
        for index, (video_key, text, likes, days_ago) in enumerate(DEMO_COMMENTS):
            post = posts.get(video_key)
            if post is None:
                continue
            # Use a stable id so re-running the seeder never duplicates rows
            # and never collides with the ids used by /comments/collect.
            platform_id = f"{post.platform_post_id}_c{index}"
            if platform_id in existing_ids:
                continue
            db.add(
                Comment(
                    platform_comment_id=platform_id,
                    post_id=post.post_id,
                    comment_text=text,
                    like_count=likes,
                    published_at=datetime.utcnow() - timedelta(days=days_ago),
                    collected_at=datetime.utcnow() - timedelta(days=days_ago),
                )
            )
            added += 1

        # Keep the stored comment_count in sync with reality
        for post in posts.values():
            post.comment_count = db.query(Comment).filter(
                Comment.post_id == post.post_id
            ).count()

        db.commit()

        print()
        print("  Demo data ready")
        print("  -----------------")
        print(f"  Creator : {creator.creator_name} (id {creator.creator_id})")
        print(f"  Videos  : {len(posts)}")
        print(f"  Comments: {db.query(Comment).filter(Comment.post_id.in_([p.post_id for p in posts.values()])).count()}")
        print()
        print("  Next: open the dashboard and press 'Run full analysis'.")
        print()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AudienceIQ with demo data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing demo data before seeding",
    )
    args = parser.parse_args()
    seed(reset=args.reset)
