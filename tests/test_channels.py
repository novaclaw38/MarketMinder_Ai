import asyncio
import json

import httpx
import pytest

from core import channels
from core.channels import Bluesky, DevTo, IndexNow, Mastodon, XTwitter
from tests.test_venture import FakeStore, IDEA, run, stub_llm  # noqa: F401
from core.venture import VentureEngine

URL = "https://site.example/blog/how-to-price"


def client_with(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_bluesky_posts_with_link_facet_and_disclosure(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "bot.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "pw")
    seen = {}

    def handler(req):
        if req.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "jwt", "did": "did:plc:1"})
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"uri": "at://did:plc:1/app.bsky.feed.post/1"})

    ref = run(Bluesky().post(client_with(handler), "Pricing a flat white", URL))
    record = seen["body"]["record"]
    facet = record["facets"][0]["index"]
    assert ref.startswith("at://")
    assert record["text"].encode()[facet["byteStart"]:facet["byteEnd"]].decode() == URL
    assert channels.DISCLOSURE in record["text"] and len(record["text"]) <= 300


def test_mastodon_and_x_and_devto(monkeypatch):
    monkeypatch.setenv("MASTODON_BASE_URL", "https://m.example")
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "t")
    monkeypatch.setenv("X_ACCESS_TOKEN", "t")
    monkeypatch.setenv("DEVTO_API_KEY", "k")
    bodies = {}

    def handler(req):
        bodies[req.url.host] = req.content.decode()
        if req.url.host == "m.example":
            return httpx.Response(200, json={"url": "https://m.example/1"})
        if req.url.host == "api.twitter.com":
            return httpx.Response(200, json={"data": {"id": "42"}})
        return httpx.Response(200, json={"url": "https://dev.to/a"})

    async def go():
        async with client_with(handler) as c:
            assert await Mastodon().post(c, "T" * 600, URL) == "https://m.example/1"
            assert await XTwitter().post(c, "T" * 600, URL) == "42"
            assert await DevTo().post(c, "Title", URL, "body") == "https://dev.to/a"
            with pytest.raises(channels.ChannelError):
                await DevTo().post(c, "Title", URL)
    run(go())
    assert "canonical_url" in bodies["dev.to"] and "written by AI" in bodies["dev.to"]


def test_indexnow_payload(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://site.example")
    monkeypatch.setenv("INDEXNOW_KEY", "abc123")
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200)

    run(IndexNow().ping(client_with(handler), URL))
    assert seen["host"] == "site.example" and seen["keyLocation"].endswith("/indexnow-key")


class FakeChannel(channels.Channel):
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.posts = fail, []

    def enabled(self):
        return True

    async def post(self, client, title, url, body=None):
        if self.fail:
            raise RuntimeError("boom")
        self.posts.append((title, url))
        return f"ref{len(self.posts)}"


def test_engine_distributes_with_daily_cap_and_isolates_failures(stub_llm, monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://site.example")
    monkeypatch.setenv("DAILY_POST_CAP_PER_CHANNEL", "2")
    monkeypatch.setenv("MAX_ACTIVE_DIVISIONS", "1")

    async def go():
        store = FakeStore()
        ok, bad = FakeChannel(), FakeChannel(fail=True)
        bad.name = "bad"
        engine = VentureEngine(store, channels=[ok, bad])
        for _ in range(4):
            await engine.tick()
        assert len(ok.posts) == 2  # product + first article, then capped
        assert all(url.startswith("https://site.example/") for _, url in ok.posts)
        failed = [d for d in store.t["distributions"] if d["status"] == "failed"]
        assert failed and all(d["channel"] == "bad" for d in failed)
    run(go())


def test_no_site_url_means_no_posting(stub_llm, monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)

    async def go():
        store = FakeStore()
        ch = FakeChannel()
        engine = VentureEngine(store, channels=[ch])
        await engine.tick()
        assert ch.posts == []
    run(go())


def test_dry_run_sends_nothing_and_logs_exact_text(stub_llm, monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://site.example")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("MAX_ACTIVE_DIVISIONS", "1")

    async def go():
        store = FakeStore()
        ch = FakeChannel()
        engine = VentureEngine(store, channels=[ch])
        await engine.tick()
        await engine.tick()
        assert ch.posts == [] and store.t["distributions"] == []
        previews = [a["summary"] for a in store.t["activity_log"] if a["kind"] == "dry_run"]
        assert previews and "would post to fake" in previews[0]
        assert "https://site.example/p/" in previews[0] and channels.DISCLOSURE in previews[0]
    run(go())


def test_previews_match_channel_limits(monkeypatch):
    long_title = "T" * 600
    assert len(Bluesky().preview(long_title, URL)) <= 300
    assert len(Mastodon().preview(long_title, URL)) <= 500
    x = XTwitter().preview(long_title, URL)
    assert len(x) - len(URL) + 23 <= 280
