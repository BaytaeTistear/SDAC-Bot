# Dashboard

The dashboard is the Flask web interface for submissions, guessing games, admin tools, server selection, theme/layout settings, and release views.

## Current Areas

- Public pages use the shared sidebar and dashboard theme.
- Discord OAuth login is available for regular users.
- Username/password admin login is still required for admin areas.
- Server selection is restricted to servers the user can access.
- Cross Server views are controlled by permissions and server visibility settings.
- Server Owners can manage their own server scope.
- Bot Owners can access all server scopes.

## Admin Areas

- Admin overview panels show users, submissions, restart/backup information, health, and release state.
- User management supports role promotion, bans, and game/submission lockouts.
- Polls can be managed from Discord and from the dashboard.
- Theme settings control site colors and background images across pages.
- Layout settings let Server Owners adjust page layout settings and use a visual test environment to drag/drop preview items and edit selected item properties.

## Sidebar

- The shared sidebar has User, Moderation, Server Owner, Bot Owner, and Cross Server sections where permissions allow.
- The menu button should sit on the sidebar edge and move with the sidebar when opened/collapsed.
- Mobile behavior should keep the sidebar usable without showing the removed top navigation bar.

## Future Updates

- Keep every new dashboard route on the shared sidebar/theme/layout shell.
- Update this page when routes, permissions, layout controls, or server visibility rules change.
