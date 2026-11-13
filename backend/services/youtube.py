"""YouTube access for AudienceIQ.

Works **without an API key** by talking to YouTube's public InnerTube JSON
endpoints (the same API the web player uses). If a YouTube Data API key is
available in ``YOUTUBE_API_KEY`` it is used instead, which gives higher
quotas and more reliable metadata.

Two things are supported:

* ``resolve``      - turn any video URL / id into metadata (title, channel,
                     views, publish date, thumbnail).
* ``fetch_comments`` - pull the top-level comments for a video.

The YouTube Data API key, when present, is used for metadata and the
InnerTube endpoint is used for comments (the Data API comment threads are
paginated differently and much slower for large videos).
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# The InnerTube endpoints work without an API key. If the operator wants to
# supply one (their own Google key, or the public YouTube web client key) it
# can be provided through the INNERTUBE_API_KEY environment variable or the
# .env file. Never hard-code a key here: repository contents are public and
# secret scanning blocks pushes containing API keys.
_INNERTUBE_KEY_ENV = "INNERTUBE_API_KEY"

_BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Read backend/.env if present, without overriding real env vars."""
    env_file = _BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _innertube_key() -> Optional[str]:
    """Return the configured InnerTube key, or None to call without one."""
    return (os.getenv(_INNERTUBE_KEY_ENV) or "").strip() or None

_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20240726.00.00",
    "hl": "en",
    "gl": "US",
}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeError(RuntimeError):
    """Raised when YouTube cannot be reached or returns an error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_video_id(value: str) -> Optional[str]:
    """Pull an 11 character video id out of a URL, id or embed code."""
    if not value:
        return None

    value = value.strip()

    if _VIDEO_ID_RE.match(value):
        return value

    # Strip a timestamp / query string and take the "v" parameter.
    parsed = urllib.parse.urlparse(value)
    if parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        if "v" in query and _VIDEO_ID_RE.match(query["v"][0]):
            return query["v"][0]
        # youtu.be/<id>
        if "youtu.be" in parsed.netloc:
            candidate = parsed.path.lstrip("/").split("/")[0]
            if _VIDEO_ID_RE.match(candidate):
                return candidate
        # /embed/<id>, /shorts/<id>, /live/<id>
        parts = [p for p in parsed.path.split("/") if p]
        if parts and _VIDEO_ID_RE.match(parts[-1]):
            return parts[-1]

    # Last resort: any 11 char token in the string.
    match = re.search(r"[A-Za-z0-9_-]{11}", value)
    if match:
        return match.group(0)
    return None


def _text_of(node: Any) -> str:
    """Read YouTube's several text shapes into a plain string."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if "simpleText" in node:
            return node["simpleText"]
        if "runs" in node:
            return "".join(run.get("text", "") for run in node["runs"])
        if "content" in node and isinstance(node["content"], str):
            return node["content"]
    return ""


def _walk(node: Any):
    """Yield every dict inside a nested JSON structure."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _innertube(endpoint: str, payload: Dict[str, Any], timeout: int = 25) -> Dict[str, Any]:
    """POST to a YouTube InnerTube endpoint and return the parsed JSON."""
    url = f"https://www.youtube.com/youtubei/v1/{endpoint}"
    key = _innertube_key()
    if key:
        url = f"{url}?key={urllib.parse.quote(key)}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.youtube.com",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:200]
        except Exception:  # pragma: no cover
            pass
        raise YouTubeError(f"YouTube returned HTTP {exc.code}. {detail}") from exc
    except urllib.error.URLError as exc:
        raise YouTubeError(f"Could not reach YouTube: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class YouTubeClient:
    """Fetch video metadata and comments from YouTube."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 25):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY") or None
        self.timeout = timeout

    # -- public API ---------------------------------------------------------

    def resolve(self, url_or_id: str) -> Dict[str, Any]:
        """Get metadata for a video URL or id.

        Returns a dict with: video_id, title, channel, channel_id, author_url,
        description, published_at, view_count, like_count, duration_seconds,
        thumbnail_url, comment_count.
        """
        video_id = extract_video_id(url_or_id)
        if not video_id:
            raise YouTubeError(
                "That does not look like a YouTube video link. "
                "Paste something like https://www.youtube.com/watch?v=XXXXXXXXXXX"
            )

        if self.api_key:
            try:
                return self._resolve_via_data_api(video_id)
            except YouTubeError:
                pass  # fall through to the keyless path

        return self._resolve_via_innertube(video_id)

    def fetch_comments(self, url_or_id: str, max_comments: int = 200) -> List[Dict[str, Any]]:
        """Fetch the top-level comments for a video.

        Each comment dict has: comment_id, text, author, author_id, likes,
        published_at, reply_count, is_pinned.
        """
        video_id = extract_video_id(url_or_id)
        if not video_id:
            raise YouTubeError("That does not look like a YouTube video link.")

        if self.api_key:
            try:
                comments = self._fetch_comments_via_data_api(video_id, max_comments)
                if comments:
                    return comments
            except YouTubeError:
                pass

        return self._fetch_comments_via_innertube(video_id, max_comments)

    def channel_videos(self, channel_id: str, max_videos: int = 20) -> List[Dict[str, Any]]:
        """List the most recent videos for a channel id."""
        data = _innertube(
            "browse",
            {
                "context": {"client": _CLIENT},
                "browseId": channel_id,
                "params": "EgZ2aWRlb3PyBgQKAjoA",
            },
            timeout=self.timeout,
        )
        return self._parse_lockup_videos(data, max_videos)

    # -- metadata: keyless -------------------------------------------------

    def _resolve_via_innertube(self, video_id: str) -> Dict[str, Any]:
        data = _innertube(
            "player",
            {"context": {"client": _CLIENT}, "videoId": video_id},
            timeout=self.timeout,
        )

        details = data.get("videoDetails") or {}
        microformat = (data.get("microformat") or {}).get("playerMicroformatRenderer") or {}

        title = details.get("title") or microformat.get("title") or ""
        channel = details.get("author") or microformat.get("ownerChannelName") or ""
        channel_id = details.get("channelId") or microformat.get("externalChannelId") or ""

        if not title:
            raise YouTubeError(
                "YouTube did not return any details for that video. "
                "It may be private, age restricted or removed."
            )

        published_at = microformat.get("publishDate") or microformat.get("uploadDate") or ""

        thumbnails = (details.get("thumbnail") or {}).get("thumbnails") or []
        thumbnail = thumbnails[-1]["url"] if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        return {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "channel_id": channel_id,
            "author_url": (
                f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
            ),
            "description": details.get("shortDescription") or "",
            "published_at": published_at,
            "view_count": _to_int(details.get("viewCount")),
            "like_count": _to_int(details.get("likeCount")),
            "duration_seconds": _to_int(details.get("lengthSeconds")),
            "thumbnail_url": thumbnail,
            "comment_count": None,
            "source": "innertube",
        }

    def _resolve_via_data_api(self, video_id: str) -> Dict[str, Any]:
        params = urllib.parse.urlencode({
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": self.api_key,
        })
        url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise YouTubeError(f"YouTube Data API returned HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise YouTubeError(f"Could not reach the YouTube Data API: {exc.reason}") from exc

        items = payload.get("items") or []
        if not items:
            raise YouTubeError("That video could not be found.")

        item = items[0]
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}

        return {
            "video_id": video_id,
            "title": snippet.get("title") or "",
            "channel": snippet.get("channelTitle") or "",
            "channel_id": snippet.get("channelId") or "",
            "author_url": f"https://www.youtube.com/channel/{snippet.get('channelId')}",
            "description": snippet.get("description") or "",
            "published_at": snippet.get("publishedAt") or "",
            "view_count": _to_int(stats.get("viewCount")),
            "like_count": _to_int(stats.get("likeCount")),
            "duration_seconds": None,
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "comment_count": _to_int(stats.get("commentCount")),
            "source": "data_api",
        }

    # -- metadata: latest channel video ------------------------------------

    def latest_video_for_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """The most recent video on a channel, if there is one."""
        videos = self.channel_videos(channel_id, max_videos=1)
        if not videos:
            return None
        return self.resolve(videos[0]["video_id"])

    # -- comments ----------------------------------------------------------

    @staticmethod
    def _continuation_tokens(node: Any) -> List[str]:
        """Collect continuation tokens in document order.

        The watch page and each comment page contain several continuations:
        the comments list itself plus one per comment thread for its replies.
        The "load more comments" continuation is the last one on the page.
        """
        tokens: List[str] = []
        for item in _walk(node):
            if "continuationItemRenderer" not in item:
                continue
            renderer = item["continuationItemRenderer"]
            token = (
                ((renderer.get("continuationEndpoint") or {}).get("continuationCommand") or {}).get("token")
            )
            if token:
                tokens.append(token)
        return tokens

    def _fetch_comments_via_innertube(
        self, video_id: str, max_comments: int
    ) -> List[Dict[str, Any]]:
        watch = _innertube(
            "next",
            {"context": {"client": _CLIENT}, "videoId": video_id},
            timeout=self.timeout,
        )

        tokens = self._continuation_tokens(watch)
        # The first page is reached through the "comments-section" token.
        token = next((t for t in tokens if "comments" in t.lower()), None)
        if not token and tokens:
            token = tokens[-1]
        if not token:
            return []

        comments: List[Dict[str, Any]] = []
        seen = set()
        pages = 0

        while token and len(comments) < max_comments and pages < 30:
            pages += 1
            page = _innertube(
                "next",
                {
                    "context": {"client": _CLIENT},
                    "videoId": video_id,
                    "continuation": token,
                },
                timeout=self.timeout,
            )

            batch, _ = self._parse_comment_page(page)
            for comment in batch:
                if comment["comment_id"] in seen:
                    continue
                seen.add(comment["comment_id"])
                comments.append(comment)
                if len(comments) >= max_comments:
                    break

            # The next "load more comments" continuation is the last one on
            # the page; the others belong to individual reply threads.
            page_tokens = self._continuation_tokens(page)
            next_token = page_tokens[-1] if page_tokens else None

            if not next_token or next_token == token:
                break
            token = next_token

        return comments

    def _parse_comment_page(self, page: Dict[str, Any]):
        """Pull comments and the next continuation out of a response page.

        YouTube returns two different shapes depending on which client you
        ask with:

        * the current web client batches comment data into
          ``frameworkUpdates.entityBatchUpdate.mutations[].payload.commentEntityPayload``
        * older clients return a plain ``commentRenderer``
        """
        comments: List[Dict[str, Any]] = []
        next_token = None

        for node in _walk(page):
            # -- current web format: batched entity payloads ---------------
            if "commentEntityPayload" in node:
                payload = node["commentEntityPayload"]
                properties = payload.get("properties") or {}
                content = properties.get("content") or {}

                text = content.get("content") or ""
                comment_id = properties.get("commentId") or ""
                if not text or not comment_id:
                    continue

                toolbar = payload.get("toolbar") or {}
                likes = _to_int(
                    toolbar.get("likeCountNotliked")
                    or toolbar.get("likeCountLiked")
                    or 0
                )

                author = properties.get("authorButtonA11y") or ""
                if author.startswith("@"):
                    author = author[1:]

                comments.append({
                    "comment_id": comment_id,
                    "text": text,
                    "author": author,
                    "author_id": "",
                    "likes": likes,
                    "published_at": properties.get("publishedTime") or "",
                    "reply_count": 0,
                    "is_pinned": False,
                })

            # -- classic format --------------------------------------------
            if "commentRenderer" in node:
                renderer = node["commentRenderer"]
                author_endpoint = (
                    (renderer.get("authorEndpoint") or {}).get("browseEndpoint") or {}
                )
                comments.append({
                    "comment_id": renderer.get("commentId") or "",
                    "text": _text_of(renderer.get("contentText")),
                    "author": _text_of(renderer.get("authorText")),
                    "author_id": author_endpoint.get("browseId", ""),
                    "likes": _to_int(_text_of(renderer.get("voteCount")) or "0"),
                    "published_at": _text_of(renderer.get("publishedTimeText")),
                    "reply_count": _to_int(_text_of(renderer.get("replyCount")) or "0"),
                    "is_pinned": bool(renderer.get("pinnedCommentBadge")),
                })

            if next_token is None and "continuationCommand" in node:
                candidate = node["continuationCommand"].get("token")
                if candidate:
                    next_token = candidate

        # De-duplicate - the same comment can appear in both formats.
        unique: List[Dict[str, Any]] = []
        seen = set()
        for comment in comments:
            if not comment["comment_id"] or comment["comment_id"] in seen:
                continue
            seen.add(comment["comment_id"])
            unique.append(comment)

        return unique, next_token

    def _fetch_comments_via_data_api(
        self, video_id: str, max_comments: int
    ) -> List[Dict[str, Any]]:
        """Fetch comments using the YouTube Data API (needs a valid key)."""
        comments: List[Dict[str, Any]] = []
        page_token = None

        while len(comments) < max_comments:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            url = f"https://www.googleapis.com/youtube/v3/commentThreads?{urllib.parse.urlencode(params)}"
            request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raise YouTubeError(f"YouTube Data API returned HTTP {exc.code}.") from exc

            for item in payload.get("items") or []:
                snippet = (item.get("snippet") or {})
                top = (snippet.get("topLevelComment") or {}).get("snippet") or {}
                comments.append({
                    "comment_id": top.get("commentId") or snippet.get("id") or "",
                    "text": top.get("textDisplay") or snippet.get("textDisplay") or "",
                    "author": top.get("authorDisplayName") or snippet.get("authorDisplayName") or "",
                    "author_id": top.get("authorChannelId", {}).get("value", ""),
                    "likes": _to_int(top.get("likeCount") or snippet.get("likeCount") or 0),
                    "published_at": top.get("publishedAt") or snippet.get("publishedAt") or "",
                    "reply_count": _to_int(snippet.get("totalReplyCount") or 0),
                    "is_pinned": bool(snippet.get("videoId") and snippet.get("parentId") == ""),
                })

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return comments

    # -- parsing ------------------------------------------------------------

    def _parse_lockup_videos(self, data: Dict[str, Any], max_videos: int) -> List[Dict[str, Any]]:
        """Read the newer ``lockupViewModel`` video entries."""
        videos: List[Dict[str, Any]] = []
        seen = set()

        for node in _walk(data):
            if "lockupViewModel" not in node:
                continue
            view = node["lockupViewModel"]
            video_id = view.get("contentId") or ""
            if not re.match(r"^[A-Za-z0-9_-]{11}$", video_id) or video_id in seen:
                continue
            seen.add(video_id)

            metadata = (view.get("metadata") or {}).get("lockupMetadataViewModel") or {}
            title = _text_of(metadata.get("title"))

            views_text = ""
            published_text = ""
            length_text = ""
            owner_text = ""

            rows = ((metadata.get("contentMetadataViewModel") or {}).get("metadataRows") or [])
            for row in rows:
                for part in row.get("metadataParts") or []:
                    text = _text_of(part.get("text"))
                    if not text:
                        continue
                    if "ago" in text or "streamed" in text or "Premiered" in text:
                        published_text = text
                    elif "view" in text.lower():
                        views_text = text
                    elif ":" in text and len(text) <= 8 and text[0].isdigit():
                        length_text = text
                    elif not owner_text and not text.endswith("ago"):
                        owner_text = text

            videos.append({
                "video_id": video_id,
                "title": title,
                "views": views_text,
                "published": published_text,
                "length": length_text,
                "owner": owner_text,
            })

            if len(videos) >= max_videos:
                break

        return videos


def _to_int(value: Any) -> Optional[int]:
    """Parse YouTube's loose numeric fields (ints, strings, "1.2K")."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return None

    multiplier = 1
    if text and text[-1] in "KMB":
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[text[-1]]
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None
