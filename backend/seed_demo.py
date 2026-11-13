"""Seed the database with a real YouTube channel, video and comments.

Run it from the backend folder:

    python seed_demo.py

The default seed is the latest **VJ Siddhu Vlogs** video. Metadata and
comments are pulled live from YouTube (no API key required - the public
InnerTube endpoints are used), so the dashboard shows genuine audience
signals instead of made up numbers.

Options::

    python seed_demo.py --video <url|id>   # seed a different video
    python seed_demo.py --comments 100     # how many comments to fetch
    python seed_demo.py --reset            # wipe the previous seed first
    python seed_demo.py --offline          # skip the network, use the fallback

The script is idempotent - re-running it updates the same rows instead of
creating duplicates.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

# YouTube titles and comments can contain any script - never let the Windows
# console encoding blow up while printing them.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - older Python versions
    pass

from database import SessionLocal, init_db  # noqa: E402
from models import User, Creator, UserCreator, Post, Comment, Commenter  # noqa: E402

# Latest VJ Siddhu Vlogs video ("Egypt Series | Ep 01"). Overridable with
# --video, so the seed can always be pointed at the newest upload.
DEFAULT_VIDEO_ID = "5j4GMySx_Ac"
DEFAULT_CHANNEL_NAME = "Vj Siddhu Vlogs"

DEMO_USER = {
    "username": "demo",
    "email": "demo@audienceiq.local",
}

# Used only when YouTube cannot be reached (offline / --offline).
FALLBACK_VIDEO = {
    "video_id": DEFAULT_VIDEO_ID,
    "title": "இப்பவே பேசிட்டா? கல்யாணத்துக்கு அப்புறம்... 😂😉😆| Egypt Series | Ep 01 | Vj Siddhu Vlogs",
    "channel": DEFAULT_CHANNEL_NAME,
    "channel_id": "UCJcCB-QYPIBcbKcBQOTwhiA",
    "description": "Seed fallback - YouTube was unreachable when this was seeded.",
    "published_at": "2026-11-11T01:30:11-08:00",
    "view_count": 2377992,
    "like_count": 0,
    "duration_seconds": 1204,
    "thumbnail_url": f"https://i.ytimg.com/vi/{DEFAULT_VIDEO_ID}/maxresdefault.jpg",
}

FALLBACK_COMMENTS = [
    ("Amazing episode as always! 🔥", 120, 0),
    ("Bro the acting is next level 😂😂", 95, 1),
    ("Waiting for the next episode immediately", 80, 1),
    ("This series is the best thing on YouTube right now", 74, 2),
    ("Placed my bets on the next part already 😬", 61, 3),
    ("Sir please make more episodes like this one", 55, 4),
    ("The comedy timing in this one is perfect 🤣", 49, 5),
    ("Not me watching this 5 times in a row", 41, 6),
    ("Vlogs episodes are always on point", 37, 7),
    ("Give this man an award already 🏆", 33, 8),
    ("The best channel on YouTube, hands down", 28, 9),
    ("New episode dropped and I am not disappointed", 24, 10),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_published_at(value) -> datetime:
    """Best effort conversion of a YouTube date string into a datetime."""
    if not value:
        return datetime.utcnow()
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text[:len(fmt) + 6].strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def fetch_from_youtube(video_ref: str, max_comments: int):
    """Return (metadata, comments) for the given video."""
    from services.youtube import YouTubeClient

    client = YouTubeClient()
    metadata = client.resolve(video_ref)
    comments = []
    try:
        comments = client.fetch_comments(video_ref, max_comments=max_comments)
    except Exception as exc:  # noqa: BLE001 - comments are optional
        print(f"[seed] Could not fetch comments: {exc}")
    return metadata, comments


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed(reset: bool = False, video_ref: str = DEFAULT_VIDEO_ID,
         max_comments: int = 60, offline: bool = False) -> None:
    max_comments = max(1, min(max_comments, 500))
    init_db()
    db = SessionLocal()

    try:
        # -- fetch the real data -------------------------------------------
        if offline:
            print("[seed] Offline mode - using the bundled fallback data.")
            metadata = dict(FALLBACK_VIDEO)
            raw_comments = [
                {
                    "comment_id": f"fallback_{i}",
                    "text": text,
                    "author": f"viewer{i}",
                    "likes": likes,
                    "published_at": "",
                }
                for i, (text, likes, days_ago) in enumerate(FALLBACK_COMMENTS)
            ]
        else:
            print(f"[seed] Fetching {video_ref} from YouTube ...")
            metadata, raw_comments = fetch_from_youtube(video_ref, max_comments)

        video_id = metadata.get("video_id") or DEFAULT_VIDEO_ID
        channel_name = metadata.get("channel") or DEFAULT_CHANNEL_NAME
        channel_id = metadata.get("channel_id") or ""
        creator_platform_id = f"yt_channel_{channel_id}" if channel_id else "yt_vj_siddhu_vlogs"
        print(f"[seed] Video : {metadata.get('title')}")
        print(f"[seed] Channel: {channel_name} ({creator_platform_id})")
        print(f"[seed] Comments fetched: {len(raw_comments)}")

        # -- clean up a previous seed --------------------------------------
        existing_creator = db.query(Creator).filter(
            Creator.platform_id == creator_platform_id
        ).first()

        if existing_creator and reset:
            print("[seed] Removing existing seeded data...")
            post_ids = [
                p.post_id
                for p in db.query(Post).filter(
                    Post.creator_id == existing_creator.creator_id
                ).all()
            ]
            if post_ids:
                comment_ids = [
                    c.comment_id
                    for c in db.query(Comment).filter(
                        Comment.post_id.in_(post_ids)
                    ).all()
                ]
                if comment_ids:
                    db.query(Comment).filter(
                        Comment.comment_id.in_(comment_ids)
                    ).delete(synchronize_session=False)
                db.query(Post).filter(Post.post_id.in_(post_ids)).delete(
                    synchronize_session=False
                )
            db.query(UserCreator).filter(
                UserCreator.creator_id == existing_creator.creator_id
            ).delete(synchronize_session=False)
            db.query(Creator).filter(
                Creator.creator_id == existing_creator.creator_id
            ).delete(synchronize_session=False)
            db.commit()
            existing_creator = None

        # -- user ----------------------------------------------------------
        user = db.query(User).filter(User.username == DEMO_USER["username"]).first()
        needs_password = not user or not (user.password_hash or "").startswith(
            ("$2a$", "$2b$", "$2y$")
        )
        if needs_password:
            import os
            import secrets

            from bcrypt import hashpw, gensalt

            # Never ship a usable credential in the source tree. Use
            # SEED_DEMO_PASSWORD when set, otherwise generate a random one and
            # print it exactly once.
            password = os.getenv("SEED_DEMO_PASSWORD") or secrets.token_urlsafe(12)
            password_hash = hashpw(
                password.encode("utf-8"), gensalt()
            ).decode("utf-8")
            if user:
                user.password_hash = password_hash
            else:
                user = User(
                    username=DEMO_USER["username"],
                    email=DEMO_USER["email"],
                    password_hash=password_hash,
                )
                db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[seed] Demo user '{user.username}' credential created.")
            print(f"[seed] One-time password: {password}")

        # -- creator -------------------------------------------------------
        creator = existing_creator
        if not creator:
            creator = Creator(
                platform_id=creator_platform_id,
                creator_name=channel_name,
                platform_type="youtube",
                description=(metadata.get("description") or "")[:1000],
                profile_image=metadata.get("thumbnail_url") or None,
            )
            db.add(creator)
            db.commit()
            db.refresh(creator)
        else:
            creator.creator_name = channel_name
            creator.description = (metadata.get("description") or "")[:1000]
            creator.profile_image = metadata.get("thumbnail_url") or creator.profile_image
            db.commit()

        if not db.query(UserCreator).filter(
            UserCreator.user_id == user.user_id,
            UserCreator.creator_id == creator.creator_id,
        ).first():
            db.add(UserCreator(user_id=user.user_id, creator_id=creator.creator_id))
            db.commit()

        # -- video ---------------------------------------------------------
        post = db.query(Post).filter(
            Post.platform_post_id == video_id
        ).first()
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        published_at = parse_published_at(metadata.get("published_at"))
        if not post:
            post = Post(creator_id=creator.creator_id, platform_post_id=video_id)
            db.add(post)
        post.creator_id = creator.creator_id
        post.title = (metadata.get("title") or "")[:500]
        post.description = metadata.get("description") or ""
        post.published_at = published_at
        post.view_count = int(metadata.get("view_count") or 0)
        post.like_count = int(metadata.get("like_count") or 0)
        post.duration_seconds = metadata.get("duration_seconds") or None
        post.thumbnail_url = metadata.get("thumbnail_url") or None
        post.watch_url = watch_url
        post.source_url = watch_url
        db.commit()
        db.refresh(post)

        # -- comments ------------------------------------------------------
        existing_ids = {
            c.platform_comment_id
            for c in db.query(Comment).filter(Comment.post_id == post.post_id).all()
        }
        added = 0
        for raw in raw_comments:
            text = (raw.get("text") or "").strip()
            if not text:
                continue
            platform_id = f"ytc_{raw.get('comment_id') or added}"
            if platform_id in existing_ids:
                continue

            commenter_id = None
            author = (raw.get("author") or "").strip()
            if author:
                author_key = f"yt_author_{author}"
                commenter = db.query(Commenter).filter(
                    Commenter.platform_commenter_id == author_key
                ).first()
                if not commenter:
                    commenter = Commenter(
                        platform_commenter_id=author_key,
                        display_name=author[:200],
                    )
                    db.add(commenter)
                    db.commit()
                    db.refresh(commenter)
                commenter_id = commenter.commenter_id

            db.add(
                Comment(
                    platform_comment_id=platform_id,
                    post_id=post.post_id,
                    commenter_id=commenter_id,
                    comment_text=text,
                    like_count=int(raw.get("likes") or 0),
                    published_at=parse_published_at(raw.get("published_at")),
                    collected_at=datetime.utcnow(),
                    author_name=author[:150] or None,
                    is_pinned=bool(raw.get("is_pinned")),
                )
            )
            existing_ids.add(platform_id)
            added += 1

        post.comment_count = db.query(Comment).filter(
            Comment.post_id == post.post_id
        ).count()
        db.commit()

        print()
        print("  Seed data ready")
        print("  -----------------")
        print(f"  Creator : {creator.creator_name} (id {creator.creator_id})")
        print(f"  Video   : {post.title}")
        print(f"  Views   : {post.view_count:,}")
        print(f"  Comments: {post.comment_count} (+{added} new)")
        print()
        print("  Next: open the dashboard and press 'Run full analysis'.")
        print()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AudienceIQ with a real YouTube video")
    parser.add_argument(
        "--video",
        default=DEFAULT_VIDEO_ID,
        help="YouTube URL or video id to seed (default: the latest VJ Siddhu Vlogs video)",
    )
    parser.add_argument(
        "--comments",
        type=int,
        default=60,
        help="How many comments to fetch (default: 60)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing seeded data before seeding",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not call YouTube - use the bundled fallback data instead",
    )
    args = parser.parse_args()
    seed(
        reset=args.reset,
        video_ref=args.video,
        max_comments=args.comments,
        offline=args.offline,
    )
