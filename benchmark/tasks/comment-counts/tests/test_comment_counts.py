"""Hidden tests for the `comment-counts` benchmark task.

The trap: the codebase already annotates `num_favorites=Count("favorites")` in
ArticleQuerySet.with_favorites(). The obvious way to add a comment count is a
second `Count("comment")` on the same queryset — which triggers a SQL cartesian
join and SILENTLY CORRUPTS BOTH counts (an article with 3 favorites and 4
comments reports 12 and 12). The correct fix requires `distinct=True` (or
subqueries).

So:
- fail_to_pass: the new comment count is present and CORRECT.
- pass_to_pass (the discriminator): the pre-existing favorite count is STILL
  correct after the change. A naive double-Count passes the new tests but
  regresses this one.

ARM-NEUTRAL: asserts the favorite count exactly as the app already exposes it —
the rendered "(N)" counter in the favorite button — and the comment count via
the rendered preview and/or the public queryset annotation. No internal names
are required beyond what the issue itself implies.

Run (identical on both arms):
    DEBUG=true DATABASE_URL=':memory:' python manage.py test countprobe
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from articles.models import Article
from comments.models import Comment

User = get_user_model()


def _u(n):
    return User.objects.create_user(email=f"{n}@x.com", username=n, password="pw12345678")


def _seed(author, title, n_fav, n_com, favoriters, commenters):
    art = Article.objects.create(author=author, title=title, summary="s", content="c")
    for u in favoriters[:n_fav]:
        art.favorites.add(u)
    for i in range(n_com):
        Comment.objects.create(article=art, author=commenters[i % len(commenters)], content=f"c{i}")
    return art


class CommentCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = _u("author")
        cls.people = [_u(f"p{i}") for i in range(6)]

    def _fav_counter_in_home(self):
        """Return the integer the home feed renders in the favorite counter."""
        resp = self.client.get(reverse("home"))
        html = resp.content.decode()
        # the favorite button renders: ...Favorite <span class="counter">(N)</span>
        m = re.search(r'counter">\((\d+)\)', html)
        return int(m.group(1)) if m else None

    # --- regression floor (pass_to_pass): favorites stay correct ---

    def test_favorite_count_correct_with_no_comments(self):
        _seed(self.author, "NoComments", 3, 0, self.people, self.people)
        self.assertEqual(self._fav_counter_in_home(), 3)

    def test_favorite_count_not_inflated_by_comments(self):
        """THE DISCRIMINATOR: 3 favorites + 4 comments must still show 3 favorites,
        not 12. A naive double-Count regresses this to 12."""
        _seed(self.author, "Mixed", 3, 4, self.people, self.people)
        self.assertEqual(
            self._fav_counter_in_home(), 3,
            "favorite count must remain correct after adding comment counts "
            "(a cartesian double-Count inflates it)",
        )

    # --- new behavior (fail_to_pass): comment count present and correct ---

    def test_comment_count_annotation_present_and_correct(self):
        """A public listing queryset must expose a correct comment count.
        Discovers the attribute name rather than hard-coding it."""
        art = _seed(self.author, "Counted", 2, 5, self.people, self.people)
        # find a queryset annotation holding the comment count, however named
        from articles.models import Article as A
        candidates = ("num_comments", "comment_count", "comments_count", "n_comments")
        # Build the same listing queryset the app uses for feeds if possible;
        # fall back to the manager's with_favorites (where favorites count lives).
        qs = A.objects.all()
        if hasattr(A.objects, "with_favorites"):
            # anonymous user is fine for counting
            from django.contrib.auth.models import AnonymousUser
            try:
                qs = A.objects.with_favorites(AnonymousUser())
            except Exception:
                qs = A.objects.all()
        obj = qs.get(pk=art.pk)
        found = [(c, getattr(obj, c)) for c in candidates if hasattr(obj, c)]
        self.assertTrue(found, f"no comment-count annotation found (tried {candidates})")
        name, val = found[0]
        self.assertEqual(val, 5, f"{name} should be 5, got {val}")

    def test_comment_count_correct_with_zero_comments(self):
        art = _seed(self.author, "Zero", 1, 0, self.people, self.people)
        from articles.models import Article as A
        from django.contrib.auth.models import AnonymousUser
        qs = A.objects.with_favorites(AnonymousUser()) if hasattr(A.objects, "with_favorites") else A.objects.all()
        obj = qs.get(pk=art.pk)
        for c in ("num_comments", "comment_count", "comments_count", "n_comments"):
            if hasattr(obj, c):
                self.assertEqual(getattr(obj, c), 0)
                return
        self.fail("no comment-count annotation found")

    def test_comment_count_rendered_in_preview(self):
        """The comment count is actually shown to the reader in the feed."""
        _seed(self.author, "Shown", 0, 7, self.people, self.people)
        resp = self.client.get(reverse("home"))
        html = resp.content.decode()
        self.assertIn("7", html, "the comment count (7) should appear in the rendered feed")

    # --- both counts correct together on the SAME article ---

    def test_both_counts_correct_simultaneously(self):
        _seed(self.author, "Both", 2, 3, self.people, self.people)
        from articles.models import Article as A
        from django.contrib.auth.models import AnonymousUser
        qs = A.objects.with_favorites(AnonymousUser()) if hasattr(A.objects, "with_favorites") else A.objects.all()
        obj = qs.get(title="Both")
        self.assertEqual(getattr(obj, "num_favorites", None), 2, "favorites must be 2")
        cc = next((getattr(obj, c) for c in ("num_comments", "comment_count", "comments_count", "n_comments") if hasattr(obj, c)), None)
        self.assertEqual(cc, 3, "comments must be 3")
