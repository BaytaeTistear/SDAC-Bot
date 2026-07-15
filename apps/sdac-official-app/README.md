# Sana-Chan Official App Scaffold

This is the first native-app scaffold for Sana-Chan. The Flask dashboard remains the backend and source of truth for login, server selection, submissions, guessing games, admin permissions, theme/layout settings, and release/update views.

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

The default dashboard URL is `https://freethefishies.us.to`. For local dashboard testing, change `.env` to `http://127.0.0.1:5000`.

Set `VITE_SDAC_DASHBOARD_URL` to the hosted dashboard URL for the Vite shell. Native builds now use the packaged app shell by default so app-only buttons such as Discord browser login, reset app login, diagnostics, and update notices are available. Only set `SDAC_APP_DIRECT_URL` before Capacitor sync if you intentionally want the old direct-dashboard WebView mode.

The app name is configurable:

```powershell
$env:SDAC_APP_NAME="Sana-Chan"
$env:SDAC_APP_ID="com.baytae.sanachan"
```

The installed Capacitor app is allowed by the dashboard by default through `capacitor://localhost`. If the app shell runs from another origin during development, set this on the Flask dashboard server:

```bash
SDAC_APP_ALLOWED_ORIGINS=http://localhost:5174,capacitor://localhost
```

## Android

Install Android Studio and the Android SDK first. Then run:

```bash
cd apps/sdac-official-app
npm install
npm run build
$env:SDAC_APP_DASHBOARD_URL="https://freethefishies.us.to"
$env:SDAC_APP_NAME="Sana-Chan"
npm run cap:add:android
npm run cap:sync
npm run cap:open:android
```

### Direct APK / Sideload Install

Use this for testing outside the Play Store:

```powershell
cd apps\sdac-official-app\android
.\gradlew assembleDebug
```

The debug APK will be under:

```text
apps/sdac-official-app/android/app/build/outputs/apk/debug/
```

Install with Android Debug Bridge:

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

### Store Install / Play Store

Use this for a Play Store upload:

```powershell
cd apps\sdac-official-app\android
.\gradlew bundleRelease
```

The release AAB will be under:

```text
apps/sdac-official-app/android/app/build/outputs/bundle/release/
```

Before uploading to the Play Store, configure a signing key in Android Studio or `android/gradle.properties`. Do not commit the keystore or keystore passwords.

### Signing The Release AAB

For Play Store/App Bundle signing, create a release keystore outside the repo:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.sdac\android-signing"
keytool -genkeypair `
  -v `
  -keystore "$env:USERPROFILE\.sdac\android-signing\Sana-Chan-release.jks" `
  -alias Sana-Chan `
  -keyalg RSA `
  -keysize 2048 `
  -validity 10000
```

Create `apps/sdac-official-app/android/keystore.properties` and do not commit it:

```properties
storeFile=C:\\Users\\YOUR_USER\\.sdac\\android-signing\\Sana-Chan-release.jks
storePassword=YOUR_STORE_PASSWORD
keyAlias=Sana-Chan
keyPassword=YOUR_KEY_PASSWORD
```

Then add signing config to `apps/sdac-official-app/android/app/build.gradle`:

```gradle
def keystorePropertiesFile = rootProject.file("keystore.properties")
def keystoreProperties = new Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
}

android {
    signingConfigs {
        release {
            if (keystorePropertiesFile.exists()) {
                storeFile file(keystoreProperties["storeFile"])
                storePassword keystoreProperties["storePassword"]
                keyAlias keystoreProperties["keyAlias"]
                keyPassword keystoreProperties["keyPassword"]
            }
        }
    }

    buildTypes {
        release {
            signingConfig signingConfigs.release
        }
    }
}
```

Build the signed bundle:

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
cd apps\sdac-official-app\android
.\gradlew bundleRelease
```

Upload `app-release.aab` to Play Console. Back up the `.jks`, alias, and passwords somewhere private; losing them can block future updates unless Play App Signing key reset is available.

## iOS

Run the same setup on macOS with Xcode installed:

```bash
cd apps/sdac-official-app
npm install
npm run build
export SDAC_APP_DASHBOARD_URL="https://freethefishies.us.to"
export SDAC_APP_NAME="Sana-Chan"
npm run cap:add:ios
npm run cap:sync
npm run cap:open:ios
```

## Desktop

For desktop, use Tauri after the mobile app is stable. Keep this same Vite app and add Tauri with:

```bash
npm create tauri-app@latest
```

Choose this existing frontend directory when prompted, then point the desktop app at the same hosted Sana-Chan dashboard URL.

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

## App Artwork

The first generated Sana-Chan artwork is saved at:

```text
apps/sdac-official-app/public/sdac-companion-art.png
```

It is an original anime companion illustration holding an SD-style baseball emblem. It intentionally avoids copying an official sports logo.


