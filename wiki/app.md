# App

SDACCompanion is the official app track for the SDAC dashboard. The current scaffold uses the Flask dashboard as the backend/source of truth.

## Current App

- App name: `SDACCompanion`
- Backend default: `https://freethefishies.us.to`
- Android debug APK and release AAB can be built from the Capacitor app scaffold.
- Discord OAuth, server selection, submissions, games, admin restrictions, theme/layout settings, and update views should stay aligned with the dashboard backend.

## Signing

Android release builds need a private keystore and `android/keystore.properties`. Do not commit the keystore or signing properties.

## Future SDK App Direction

Future updates should remove the web-wrapper app approach and move to the SDK app approach. Keep the Flask backend as the source of truth, but build app screens and integrations through the SDK app path instead of simply wrapping the dashboard.

## Update Scope

- Use `App update` for app-only work.
- Use `Bot and App update` when app changes also require backend, bot, release, or dashboard changes.
