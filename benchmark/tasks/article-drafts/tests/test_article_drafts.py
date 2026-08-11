"""Hidden invariant tests for the `article-drafts` benchmark task.

ARM-NEUTRAL BY CONSTRUCTION: every assertion drives a public URL (via reverse())
or the public ORM, and asserts only spec-level behavior — "a draft is not
publicly visible, but its author can see it." No test references any internal
helper, module layout, or arm-specific structure. Either arm passes iff it
actually implements draft visibility correctly across all surfaces.

Behavioral contract (from the RealWorld/Conduit spec + Django conventions):
  - Article gains an `is_published` boolean, default True (existing articles
    stay visible after migration).
  - A draft (is_published=False) is excluded from every PUBLIC listing:
    global feed, following feed, tag listing, and the author's profile as
    seen by another user.
  - A draft's detail page is not visible to a non-author (403 or 404).
  - The author CAN still see their own draft's detail page (not over-filtered).

Run (identical on both arms):
    DEBUG=true DATABASE_URL=':memory:' python manage.py test drafts_probe
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from articles.models import Article

User = get_user_model()


def _mk_user(username, email=None):
    return User.objects.create_user(
        email=email or f"{username}@example.com",
        username=username,
        password="pw12345678",
    )


def _mk_article(author, title, *, is_published=True, tag=None):
    """Create an article, tolerant of how draft state is exposed.

    Prefers the `is_published` field (the spec'd contract). Sets it after
    create() so a NOT-NULL default migration is exercised. Adds a tag if the
    project supports tagging.
    """
    art = Article.objects.create(
        author=author, title=title, summary="s", content="c"
    )
    # Set publish state via the field the task is required to add.
    if hasattr(art, "is_published"):
        art.is_published = is_published
        art.save()
    if tag is not None and hasattr(art, "tags"):
        art.tags.add(tag)
    return art


class DraftVisibilityTests(TestCase):
    def setUp(self):
        self.author = _mk_user("alice")
        self.other = _mk_user("bob")

    # --- regression floor: published articles behave as before ---

    def test_is_published_defaults_true(self):
        """A freshly created article with no explicit flag is published."""
        art = Article.objects.create(
            author=self.author, title="Plain", summary="s", content="c"
        )
        self.assertTrue(
            getattr(art, "is_published", True),
            "new articles must default to published (existing content stays visible)",
        )

    def test_published_article_still_listed(self):
        _mk_article(self.author, "Public Post", is_published=True)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Public Post")

    # --- the five visibility surfaces a naive impl may leak ---

    def test_draft_excluded_from_global_feed(self):
        _mk_article(self.author, "Secret Draft", is_published=False)
        resp = self.client.get(reverse("home"))
        self.assertNotContains(resp, "Secret Draft")

    def test_draft_excluded_from_following_feed(self):
        # bob follows alice; alice's draft must not appear in bob's following feed
        self.author.followers.add(self.other)
        _mk_article(self.author, "Followed Draft", is_published=False)
        self.client.force_login(self.other)
        resp = self.client.get(reverse("home") + "?feed=following")
        self.assertNotContains(resp, "Followed Draft")

    def test_draft_excluded_from_tag_listing(self):
        _mk_article(self.author, "Tagged Draft", is_published=False, tag="python")
        resp = self.client.get(reverse("tag", kwargs={"tag": "python"}))
        self.assertNotContains(resp, "Tagged Draft")

    def test_draft_hidden_on_authors_public_profile(self):
        _mk_article(self.author, "Profile Draft", is_published=False)
        # another user viewing alice's profile must not see alice's draft
        self.client.force_login(self.other)
        resp = self.client.get(
            reverse("profile", kwargs={"username": self.author.username})
        )
        self.assertNotContains(resp, "Profile Draft")

    def test_draft_not_visible_to_other_user_by_url(self):
        art = _mk_article(self.author, "URL Draft", is_published=False)
        self.client.force_login(self.other)
        resp = self.client.get(
            reverse("article_detail", kwargs={"slug": art.slug})
        )
        self.assertIn(
            resp.status_code, (403, 404),
            "a non-author must not be able to read a draft by its direct URL",
        )

    # --- guard against over-correction: author keeps access ---

    def test_author_sees_own_draft_in_detail(self):
        art = _mk_article(self.author, "My Own Draft", is_published=False)
        self.client.force_login(self.author)
        resp = self.client.get(
            reverse("article_detail", kwargs={"slug": art.slug})
        )
        self.assertEqual(
            resp.status_code, 200,
            "the author must still be able to view their own draft",
        )
