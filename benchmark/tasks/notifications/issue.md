# Add a notifications system

Users should be notified about activity involving them. Add notifications so that
a user is notified when another user:

- **follows** them,
- **favorites** one of their articles, or
- **comments** on one of their articles.

Requirements:
- Show each user an **unread notification count** in the site navigation.
- Add a **notifications page** where a user sees their notifications, newest
  first, and can **mark them as read** (which updates the unread count).
- A user is **never** notified about their own actions (favoriting or commenting
  on your own article, etc.).
- Reversing an action (unfollowing, unfavoriting) must **not** generate a
  notification.

Implement this feature in the codebase.
