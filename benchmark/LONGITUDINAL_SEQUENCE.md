# The feature sequence — actually designed

This is the concrete, ordered, interdependent sequence for the longitudinal
experiment (companion to LONGITUDINAL_DESIGN.md). It is engineered so that each
feature's *naive* implementation has a specific, identifiable way to break a
*specific earlier* feature — that collision is the measured signal. Not a list of
names; a dependency graph with named failure modes.

## The shared collision surface

Every article-listing feature collides here. The app has ~4 independent read
paths, each doing its own `Article.objects` query:

- **R1** global feed (`_build_feed`, no filter)
- **R2** following feed (`_build_feed` + `author__in=followed`)
- **R3** tag feed (`_build_feed` + `tags__name`)
- **R4** profile "my articles" (`accounts.views`, `author=profile_user`)
- **R5** profile "favorited" (`accounts.views`, `favorites=profile_user`)
- **D** article detail (`get(slug=...)`)

A feature that changes *what should be visible* must be applied at ALL relevant
read paths. A naive impl applies it at the one path the issue mentions and misses
the rest — and that miss only surfaces when a LATER feature's test exercises the
missed path. That lag is the tech-debt dynamic.

---

## The sequence (each: what it adds · what it stresses · the naive-break)

### F1 — Drafts  (`is_published` on Article)
- **Adds:** draft/publish; drafts hidden from public listings.
- **Introduces the invariant:** "unpublished ⇒ absent from R1–R5, guarded at D."
- **Stresses:** nothing yet (first feature).
- **Regression tests it plants for later:** draft-hidden checks at R1–R5 + D.
  These become the pass_to_pass burden every later feature must not break.

### F2 — Reading list / bookmarks  (per-user M2M on Article, like favorites)
- **Adds:** bookmark an article; a "reading list" page listing bookmarked ones.
- **Stresses F1:** the reading-list page is a NEW read path (R6). A naive impl
  lists bookmarked articles **without the `is_published` filter** → a user's
  bookmarked-then-unpublished article leaks on the reading list.
- **Naive-break:** F1's draft-invisibility regresses at the new R6 path.
- **Why C should hold:** F1's spec says "drafts are absent from listings"; the
  FFFlow arm carries that spec and applies it to the new listing.

### F3 — Comment counts on listings  (annotate `num_comments`)
- **Adds:** comment count in every article preview.
- **Stresses F1+F2:** the annotation must be added to the SAME querysets that F1
  filtered and F2 introduced — including R6. Also the cartesian-Count trap with
  the existing `num_favorites` (needs `distinct=True`).
- **Naive-break (two ways):** (a) corrupts `num_favorites` via cartesian join
  (breaks pre-existing favorites display); (b) adds the count to R1 but not R4/R6,
  so counts are inconsistent across paths.

### F4 — User blocking  (block gates interaction)
- **Adds:** block; blocked user can't follow/comment/favorite the blocker.
- **Stresses F1,F2,F3:** blocking adds a filter to read paths ("hide blocked
  authors' articles from my feed" — if that's in scope) that must compose with
  the draft filter AND the annotations. The comment guard must not break F3's
  comment-count query.
- **Naive-break:** applies the block filter to R1 only; blocked authors' articles
  still appear on R3 (tag), R6 (reading list). OR the block-comment guard changes
  comment creation in a way that throws off F3's counts.

### F5 — Notifications  (follow/favorite/comment triggers)
- **Adds:** notify on follow/favorite/comment; unread badge; page; mark-read.
- **Stresses F4:** the favorite/comment trigger sites are the SAME views F4 added
  block-guards to. A naive impl wires a notification on comment **even when F4
  should have blocked that comment** → blocked user's rejected comment still
  notifies (F4 regresses: interaction that shouldn't happen fires a side effect).
- **Naive-break:** notification fires inside/after a blocked action; or self-
  notification returns after F4's refactor moved the author check.

### F6 — Tag following  (users follow tags; feed includes them)
- **Adds:** follow a tag; following-feed includes followed-tag articles.
- **Stresses F1,F4:** the expanded following-feed query must STILL exclude drafts
  (F1) and blocked authors (F4). This is the classic "widen a query, forget the
  existing filters" break.
- **Naive-break:** followed-tag articles bypass the draft filter and/or block
  filter because the new OR-branch was added without re-applying them.

### F7 — Article revisions  (editing creates revisions; publish promotes)
- **Adds:** an article has revisions; public sees last-published revision, author
  sees working copy. Model redesign + data migration of existing articles.
- **Stresses EVERYTHING (F1,F3,F4,F6):** every read path now must resolve
  "which revision," while STILL honoring drafts, counts, blocks, tag-following.
  This is the feature that forces the whole accumulated invariant set through a
  structural change.
- **Naive-break:** high surface. Likely breaks comment-count (counts attach to
  article vs revision), draft visibility (is_published moves to revision), or
  favorite counts. The arm that documented these invariants (C) has a checklist;
  the naive arm rediscovers them by breaking them.

### F8 — Moderation / report-and-hide  (report → hide from public)
- **Adds:** report an article; reported+actioned articles hidden from public.
- **Stresses F1,F4,F6,F7:** "hidden" is a THIRD visibility dimension stacking on
  draft (F1) and block (F4), across all read paths incl. tag-following (F6) and
  resolved through revisions (F7).
- **Naive-break:** the hide filter composes with some read paths but not all; or
  conflicts with the revision resolution from F7.

---

## Why this ordering

The visibility invariant compounds: F1 (draft) → F4 (block) → F6 (tag-follow
widens) → F7 (revisions resolve) → F8 (hide stacks). By F8 a correct feed query
must simultaneously honor FOUR independent visibility rules across ~6 read paths.
Each feature adds one rule or one path; the naive arm's odds of keeping ALL prior
rules correct at ALL paths decay multiplicatively — which is precisely the
"tech debt compounds" curve we want to plot. The FFFlow arm's specs encode each
rule as it's introduced, giving the later features a checklist the naive arm
lacks.

## The measurable prediction
- **Cumulative regression:** A's passing-test count peels off starting around
  F2–F3 (first missed read path) and accelerates through F6–F8; C stays near
  100%.
- **If both stay near 100%:** the thesis fails at this horizon — a real result.
  (Would suggest the model re-derives invariants from code each time well enough
  that written specs add no marginal safety.)

## Minimum viable version (if 8 is too much)
Run **F1 → F2 → F3 → F4** only. That already chains: draft invariant (F1),
new-read-path break (F2), annotation+cartesian (F3), multi-path filter (F4). The
first divergence, if it exists, should appear by F4. Four features × 2 arms ×
2 models is a tractable first run.
