"""
Distribution channels. Each adapter is enabled only when its credentials are in the environment.

Rules that apply to every channel (enforced by VentureEngine.distribute):
- original posts only: no replies, DMs, follows, mentions or mass tagging
- every post discloses that it is AI-written
- a per-division daily cap per channel
"""

import os
from typing import List, Optional

import httpx

DISCLOSURE = "(AI-written)"


class ChannelError(RuntimeError):
    pass


class Channel:
    name = "channel"
    supports_articles = True

    def enabled(self) -> bool:
        raise NotImplementedError

    def compose(self, title: str, url: str, max_len: int) -> str:
        tail = f"\n{url}\n{DISCLOSURE}"
        room = max_len - len(tail)
        head = title if len(title) <= room else title[: room - 1].rstrip() + "…"
        return head + tail

    async def post(self, client: httpx.AsyncClient, title: str, url: str, body: Optional[str] = None) -> str:
        """Publishes and returns an external reference (URL or id)."""
        raise NotImplementedError


class Bluesky(Channel):
    name = "bluesky"

    def enabled(self) -> bool:
        return bool(os.environ.get("BLUESKY_HANDLE") and os.environ.get("BLUESKY_APP_PASSWORD"))

    async def post(self, client, title, url, body=None):
        host = os.environ.get("BLUESKY_HOST", "https://bsky.social")
        session = await client.post(f"{host}/xrpc/com.atproto.server.createSession", json={
            "identifier": os.environ["BLUESKY_HANDLE"], "password": os.environ["BLUESKY_APP_PASSWORD"]})
        session.raise_for_status()
        s = session.json()

        text = self.compose(title, url, 300)
        start = len(text[: text.index(url)].encode("utf-8"))
        record = {
            "$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
            "createdAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "facets": [{
                "index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }],
        }
        res = await client.post(
            f"{host}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {s['accessJwt']}"},
            json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": record})
        res.raise_for_status()
        return res.json()["uri"]


class Mastodon(Channel):
    name = "mastodon"

    def enabled(self) -> bool:
        return bool(os.environ.get("MASTODON_BASE_URL") and os.environ.get("MASTODON_ACCESS_TOKEN"))

    async def post(self, client, title, url, body=None):
        res = await client.post(
            f"{os.environ['MASTODON_BASE_URL'].rstrip('/')}/api/v1/statuses",
            headers={"Authorization": f"Bearer {os.environ['MASTODON_ACCESS_TOKEN']}"},
            data={"status": self.compose(title, url, 500), "visibility": "public", "language": "en"})
        res.raise_for_status()
        return res.json()["url"]


class XTwitter(Channel):
    name = "x"

    def enabled(self) -> bool:
        return bool(os.environ.get("X_ACCESS_TOKEN"))

    async def post(self, client, title, url, body=None):
        # X counts every link as 23 characters
        text = self.compose(title, url, 280 - len(url) + 23)
        res = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {os.environ['X_ACCESS_TOKEN']}"},
            json={"text": text})
        res.raise_for_status()
        return res.json()["data"]["id"]


class DevTo(Channel):
    """Cross-posts full articles with a canonical URL pointing back to our own page."""
    name = "devto"

    def enabled(self) -> bool:
        return bool(os.environ.get("DEVTO_API_KEY"))

    async def post(self, client, title, url, body=None):
        if not body:
            raise ChannelError("devto only carries articles")
        footer = f"\n\n---\n*This article was written by AI. Original: {url}*"
        res = await client.post(
            "https://dev.to/api/articles",
            headers={"api-key": os.environ["DEVTO_API_KEY"]},
            json={"article": {"title": title, "body_markdown": body + footer,
                              "published": True, "canonical_url": url}})
        res.raise_for_status()
        return res.json()["url"]


class IndexNow:
    """Tells Bing, Yandex and others about new URLs immediately. Needs SITE_URL and INDEXNOW_KEY."""

    def enabled(self) -> bool:
        return bool(os.environ.get("INDEXNOW_KEY") and os.environ.get("SITE_URL"))

    async def ping(self, client: httpx.AsyncClient, url: str) -> None:
        site = os.environ["SITE_URL"].rstrip("/")
        res = await client.post("https://api.indexnow.org/indexnow", json={
            "host": site.split("://", 1)[-1], "key": os.environ["INDEXNOW_KEY"],
            "keyLocation": f"{site}/indexnow-key", "urlList": [url]})
        res.raise_for_status()


def build_channels() -> List[Channel]:
    return [c for c in (Bluesky(), Mastodon(), XTwitter(), DevTo()) if c.enabled()]
