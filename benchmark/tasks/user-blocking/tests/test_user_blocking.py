"""Hidden invariant tests for the `user-blocking` benchmark task.

ARM-NEUTRAL: every assertion drives a public URL (reverse()) or the public ORM,
asserting only spec-level behavior. No reference to internal helpers or arm
structure. This is a `system`-complexity feature: a correct implementation must
touch the follow view, the feed, the comment view, and the favorite view — four
apps — and keep several invariants simultaneously.

Behavioral contract ("A blocks B" means the A<->B interaction channel is cut,
B-side; everyone else is unaffected):
  1. Blocking removes any existing follow edge in EITHER direction.
  2. B cannot follow A after being blocked.
  3. A's articles do not appear in B's feeds.
  4. B cannot comment on A's articles.
  5. B cannot favorite A's articles.
  6. A does not count B among A's followers after blocking.
  7. A's own experience of the app is otherwise normal (not over-blocked).
  8. Unrelated users are completely unaffected (filter not too broad).

The task is required to expose blocking somehow; tests discover the mechanism
through public behavior (follow endpoint rejection, feed absence, 403/404 on
interaction) rather than a specific internal API, so any correct design passes.

Run (identical on both arms):
    DEBUG=true DATABASE_URL=':memory:' python manage.py test blocking_probe
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from articles.models import Article

User = get_user_model()


def _u(name):
    return User.objects.create_user(
        email=f"{name}@example.com", username=name, password="pw12345678"
    )


def _article(author, title):
    return Article.objects.create(author=author, title=title, summary="s", content="c")


def _follow(follower, target):
    """follower follows target (target.followers gains follower)."""
    target.followers.add(follower)


def _block(blocker, blocked, client):
    """Best-effort: perform a block via whatever URL the feature exposes.

    Tries common url names; falls back to any model-level relation the task
    added. Tests assert BEHAVIOR, so as long as a block is established somehow,
    the downstream invariants must hold.
    """
    client.force_login(blocker)
    for name in ("block", "block_user", "user_block", "profile_block"):
        try:
            url = reverse(name, kwargs={"username": blocked.username})
        except Exception:
            continue
        resp = client.post(url)
        if resp.status_code in (200, 201, 204, 302):
            return True
    # fallback: model relation named blocked/blocks/blocked_users
    blocker.refresh_from_db()
    for attr in ("blocked_users", "blocked", "blocks"):
        rel = getattr(blocker, attr, None)
        if rel is not None and hasattr(rel, "add"):
            rel.add(blocked)
            return True
    return False


class UserBlockingTests(TestCase):
    def setUp(self):
        self.alice = _u("alice")   # A — the blocker
        self.bob = _u("bob")       # B — gets blocked
        self.carol = _u("carol")   # unrelated control

    # 1. blocking removes existing follows in either direction
    def test_block_removes_existing_follow_either_direction(self):
        _follow(self.bob, self.alice)   # bob follows alice
        _follow(self.alice, self.bob)   # alice follows bob
        assert _block(self.alice, self.bob, self.client), "no block mechanism found"
        self.alice.refresh_from_db(); self.bob.refresh_from_db()
        self.assertFalse(
            self.alice.followers.filter(pk=self.bob.id).exists(),
            "bob must no longer follow alice after alice blocks bob",
        )
        self.assertFalse(
            self.bob.followers.filter(pk=self.alice.id).exists(),
            "alice's follow of bob must also be severed",
        )

    # 2. B cannot follow A after being blocked
    def test_blocked_user_cannot_follow_blocker(self):
        assert _block(self.alice, self.bob, self.client)
        self.client.force_login(self.bob)
        self.client.post(reverse("follow", kwargs={"username": self.alice.username}))
        self.alice.refresh_from_db()
        self.assertFalse(
            self.alice.followers.filter(pk=self.bob.id).exists(),
            "a blocked user must not be able to follow the blocker",
        )

    # 3. A's articles absent from B's feeds
    def test_blocker_articles_absent_from_blocked_feed(self):
        _article(self.alice, "Alice Post")
        assert _block(self.alice, self.bob, self.client)
        self.client.force_login(self.bob)
        resp = self.client.get(reverse("home"))
        self.assertNotContains(resp, "Alice Post")

    # 4. B cannot comment on A's articles
    def test_blocked_user_cannot_comment(self):
        art = _article(self.alice, "Alice Post")
        assert _block(self.alice, self.bob, self.client)
        self.client.force_login(self.bob)
        resp = self.client.post(
            reverse("comment_create", kwargs={"slug": art.slug}),
            {"body": "intrusion", "content": "intrusion"},
        )
        self.assertIn(
            resp.status_code, (403, 404),
            "a blocked user must not be able to comment on the blocker's article",
        )

    # 5. B cannot favorite A's articles
    def test_blocked_user_cannot_favorite(self):
        art = _article(self.alice, "Alice Post")
        assert _block(self.alice, self.bob, self.client)
        self.client.force_login(self.bob)
        self.client.post(reverse("article_favorite", kwargs={"slug": art.slug}))
        art.refresh_from_db()
        self.assertFalse(
            art.favorites.filter(pk=self.bob.id).exists(),
            "a blocked user must not be able to favorite the blocker's article",
        )

    # 6. A doesn't count B as a follower after blocking
    def test_blocker_follower_count_excludes_blocked(self):
        _follow(self.bob, self.alice)
        assert _block(self.alice, self.bob, self.client)
        self.alice.refresh_from_db()
        self.assertNotIn(
            self.bob, list(self.alice.followers.all()),
            "blocked user must not remain in the blocker's followers",
        )

    # 7. A's own experience is otherwise normal (not over-blocked)
    def test_blocker_feed_still_works(self):
        _article(self.carol, "Carol Post")
        assert _block(self.alice, self.bob, self.client)
        self.client.force_login(self.alice)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Carol Post", msg_prefix="blocking bob must not break alice's normal feed")

    # 8. unrelated users unaffected (filter not too broad)
    def test_unrelated_users_unaffected(self):
        _article(self.alice, "Alice Post")
        assert _block(self.alice, self.bob, self.client)
        # carol (unrelated) must still see alice's article and be able to follow
        self.client.force_login(self.carol)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Alice Post", msg_prefix="unrelated carol must still see alice's article")
        self.client.post(reverse("follow", kwargs={"username": self.alice.username}))
        self.alice.refresh_from_db()
        self.assertTrue(
            self.alice.followers.filter(pk=self.carol.id).exists(),
            "unrelated user carol must still be able to follow alice",
        )
