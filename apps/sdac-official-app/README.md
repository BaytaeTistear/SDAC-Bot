# SDAC Official App Scaffold

This is the first native-app scaffold for SDAC. The Flask dashboard remains the backend and source of truth for login, server selection, submissions, guessing games, admin permissions, theme/layout settings, and release/update views.

## Recommendation

Use Capacitor first.

- Capacitor is the fastest path to an official iOS and Android app because SDAC already has a working responsive dashboard and PWA routes.
- Tauri is the best later desktop wrapper if you want smaller Windows/macOS/Linux desktop builds.
- Electron works, but it is heavier than Tauri for this app.
- React Native would require rebuilding most dashboard screens and duplicating behavior.
- Discord Embedded App SDK is only the right choice for an in-Discord activity, not a normal app-store app.

## Development

```bash
cd apps/sdac-official-app
npm install
copy .env.example .env
npm run dev
```

Set `VITE_SDAC_DASHBOARD_URL` to the hosted dashboard URL. For native builds, set `SDAC_APP_DASHBOARD_URL` before running Capacitor sync so the native app opens the hosted dashboard directly.

If the app shell runs from a different origin than the dashboard during development, set this on the Flask dashboard server:

```bash
SDAC_APP_ALLOWED_ORIGINS=http://localhost:5174,capacitor://localhost
```

## Android

```bash
cd apps/sdac-official-app
npm install
npm run build
$env:SDAC_APP_DASHBOARD_URL="https://your-sdac-domain.example"
npm run cap:add:android
npm run cap:sync
npm run cap:open:android
```

## iOS

Run the same setup on macOS with Xcode installed:

```bash
cd apps/sdac-official-app
npm install
npm run build
export SDAC_APP_DASHBOARD_URL="https://your-sdac-domain.example"
npm run cap:add:ios
npm run cap:sync
npm run cap:open:ios
```

## Desktop

For desktop, use Tauri after the mobile app is stable. Keep this same Vite app and add Tauri with:

```bash
npm create tauri-app@latest
```

Choose this existing frontend directory when prompted, then point the desktop app at the same hosted SDAC dashboard URL.

## Backend Contract

The scaffold uses:

- `GET /api/app/bootstrap` for app metadata, auth/session state, theme, layout, server access, useful routes, and release info.
- Existing HTML routes for all real workflows.
- Existing public APIs: `/api/stats`, `/api/servers`, `/api/leaderboard`, `/api/server/<guild_id>`.

## Backend API Gaps To Add Later

The current app shell can ship as a wrapper. A full native UI would need these additional JSON APIs:

- `GET /api/app/submissions?guild_id=&page=&sort=`
- `GET /api/app/my-submissions?guild_id=&page=`
- `POST /api/app/submissions/<id>/vote`
- `GET /api/app/guessing/leaderboard?guild_id=&month=`
- `GET /api/app/guessing/games?guild_id=`
- `POST /api/app/guessing/games/<id>/guess`
- `GET /api/app/admin/overview`
- `GET /api/app/admin/users`
- `POST /api/app/admin/users/<username>/role`
- `POST /api/app/admin/users/<username>/lockout`
- `GET /api/app/admin/theme`
- `POST /api/app/admin/theme`
- `GET /api/app/admin/layout`
- `POST /api/app/admin/layout`
- `GET /api/app/admin/releases`
- `POST /api/app/admin/releases/test-notification`

Keep admin APIs protected by the existing dashboard login/session, CSRF strategy, and per-server role checks.
