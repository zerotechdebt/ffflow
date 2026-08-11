# Add draft support to articles

Add a **draft** capability to articles. An author should be able to save an
article as a draft while they're still working on it, and publish it when it's
ready.

Requirements:
- Add an `is_published` boolean to the `Article` model. Existing articles must
  remain published (default published), so nothing that is currently visible
  disappears.
- Let the article editor set whether an article is published or a draft.
- Give an author a way to see their own drafts.

Implement this feature in the codebase.
