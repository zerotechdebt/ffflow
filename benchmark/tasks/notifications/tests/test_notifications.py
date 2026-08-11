"""Behavioral tests for the `notifications` benchmark task (fail_to_pass).

ARM-NEUTRAL and IMPLEMENTATION-NEUTRAL: everything is asserted through public
behavior — perform an action via its real URL, then assert the target user's
notification state through whatever public surface the feature exposes. We do
NOT assume a model name, field names, or a specific queryset. Two discovery
helpers find "the target user's notifications" and "the unread count" by trying
the common shapes an implementation might use, and fall back to the rendered
notifications page / nav. If a correct implementation exists in ANY reasonable
shape, these pass.

The existing-behavior regression guard (pass_to_pass) is the project's own test
suite run under pytest — see run_notifications.sh. This file only covers the
NEW behavior.

Run:  DEBUG=true DATABASE_URL=':memory:' python manage.py test notifprobe
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse, NoReverseMatch

from articles.models import Article

User = get_user_model()


def _u(n):
    return User.objects.create_user(email=f"{n}@x.com", username=n, password="pw12345678")


def _article(author, title="Post"):
    return Article.objects.create(author=author, title=title, summary="s", content="c")


# ---- discovery helpers: find notification state without assuming the schema ----

def _notif_url():
    for name in ("notifications", "notification_list", "notifications_list", "inbox"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return None


def _notifications_for(user):
    """Best-effort queryset/list of a user's notifications, schema-agnostic."""
    # reverse relations / attributes an implementation is likely to expose
    for attr in ("notifications", "notification_set", "received_notifications"):
        rel = getattr(user, attr, None)
        if rel is not None and hasattr(rel, "all"):
            return list(rel.all())
    # fall back: a Notification model with a recipient-like FK
    try:
        from django.apps import apps
        for model in apps.get_models():
            if "notification" in model.__name__.lower():
                for fld in ("recipient", "user", "to_user", "target", "receiver", "owner"):
                    if any(f.name == fld for f in model._meta.get_fields()):
                        return list(model.objects.filter(**{fld: user}))
    except Exception:
        pass
    return None


def _unread_count_in_nav(client, user):
    """Render a page as `user` and extract an unread badge integer if present."""
    client.force_login(user)
    resp = client.get(reverse("home"))
    html = resp.content.decode()
    # look for a notifications link/badge with a number near it
    for pat in (
        r'notification[^<]*?(\d+)',
        r'badge[^>]*>\s*(\d+)',
        r'unread[^<]*?(\d+)',
    ):
        m = re.search(pat, html, re.I)
        if m:
            return int(m.group(1))
    return None


def _unread_count(client, user):
    """Unread count via nav; fall back to counting unread-ish notifications."""
    n = _unread_count_in_nav(client, user)
    if n is not None:
        return n
    notifs = _notifications_for(user) or []
    unread = [x for x in notifs if not getattr(x, "read", getattr(x, "is_read", False))]
    return len(unread)


class NotificationBehaviorTests(TestCase):
    def setUp(self):
        self.alice = _u("alice")   # actor
        self.bob = _u("bob")       # recipient
        self.client_ = self.client

    # 1. follow -> notifies followee
    def test_follow_notifies_target(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        notifs = _notifications_for(self.bob)
        self.assertTrue(notifs, "bob should have a notification after alice follows him")

    # 2. favorite -> notifies article author
    def test_favorite_notifies_author(self):
        art = _article(self.bob, "Bob Post")
        self.client.force_login(self.alice)
        self.client.post(reverse("article_favorite", kwargs={"slug": art.slug}))
        self.assertTrue(_notifications_for(self.bob),
                        "bob should be notified when alice favorites his article")

    # 3. comment -> notifies article author
    def test_comment_notifies_author(self):
        art = _article(self.bob, "Bob Post")
        self.client.force_login(self.alice)
        self.client.post(reverse("comment_create", kwargs={"slug": art.slug}),
                         {"body": "nice", "content": "nice"})
        self.assertTrue(_notifications_for(self.bob),
                        "bob should be notified when alice comments on his article")

    # 4. no self-notification
    def test_no_self_notification(self):
        art = _article(self.alice, "Own Post")
        self.client.force_login(self.alice)
        self.client.post(reverse("article_favorite", kwargs={"slug": art.slug}))
        self.client.post(reverse("comment_create", kwargs={"slug": art.slug}),
                         {"body": "self", "content": "self"})
        notifs = _notifications_for(self.alice) or []
        self.assertEqual(len(notifs), 0,
                         "a user must not be notified about their own actions")

    # 5. unread count reflects unread notifications
    def test_unread_count_reflects_notifications(self):
        # two distinct actors act on bob
        carol = _u("carol")
        self.client.force_login(self.alice)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        self.client.force_login(carol)
        art = _article(self.bob, "Bob Post")
        self.client.post(reverse("article_favorite", kwargs={"slug": art.slug}))
        self.assertEqual(_unread_count(self.client, self.bob), 2,
                         "bob's unread count should be 2")

    # 6. notifications page lists newest-first
    def test_notifications_page_newest_first(self):
        url = _notif_url()
        self.assertIsNotNone(url, "a notifications page URL must exist")
        # generate two notifications with distinguishable actors
        self.client.force_login(self.alice)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        carol = _u("carol")
        self.client.force_login(carol)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        self.client.force_login(self.bob)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # newest (carol) should appear before oldest (alice) in the document
        i_carol, i_alice = html.find("carol"), html.find("alice")
        self.assertTrue(i_carol != -1 and (i_alice == -1 or i_carol < i_alice),
                        "notifications should be listed newest-first")

    # 7. mark read decrements unread count
    def test_mark_read_decrements_unread(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        before = _unread_count(self.client, self.bob)
        self.assertGreaterEqual(before, 1)
        # mark read via the notifications page's mark-read action, discovered
        marked = False
        for name in ("notifications_mark_read", "notification_mark_read",
                     "mark_notifications_read", "notifications_read", "mark_read"):
            try:
                url = reverse(name)
            except NoReverseMatch:
                # maybe it takes a pk
                notifs = _notifications_for(self.bob) or []
                if notifs:
                    for nm in ("notification_mark_read", "notification_read", "mark_read"):
                        try:
                            url = reverse(nm, kwargs={"pk": notifs[0].pk})
                        except NoReverseMatch:
                            continue
                        self.client.force_login(self.bob)
                        self.client.post(url); marked = True; break
                if marked:
                    break
                continue
            self.client.force_login(self.bob)
            self.client.post(url); marked = True; break
        self.assertTrue(marked, "a mark-read action must exist")
        after = _unread_count(self.client, self.bob)
        self.assertLess(after, before, "unread count must drop after marking read")

    # 8. reversing an action does not create a spurious notification
    def test_unfollow_does_not_notify(self):
        self.client.force_login(self.alice)
        # follow then unfollow (same endpoint toggles)
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        self.client.post(reverse("follow", kwargs={"username": self.bob.username}))
        notifs = _notifications_for(self.bob) or []
        # at most the single follow notification; the unfollow must not add one
        self.assertLessEqual(len(notifs), 1,
                             "unfollowing must not create an additional notification")
