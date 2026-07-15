# Sana-Chan Google Play Upload Checklist

Generated on 2026-07-15.

## Current Build Output

Built release bundle:

```text
apps/sdac-official-app/android/app/build/outputs/bundle/release/app-release.aab
```

Checksum file:

```text
apps/sdac-official-app/android/app/build/outputs/bundle/release/app-release.aab.sha256
```

SHA256:

```text
84D6B5550121637E2E518BA37840EAFB6AB4DFB432A3F9B7E6835BB3BAD877F2  app-release.aab
```

Signing status: `jarsigner -verify -verbose -certs app\build\outputs\bundle\release\app-release.aab` reports `jar verified`.

Important: this generated `app-release.aab` is signed with the local Sana-Chan upload key. Keep the private keystore and `keystore.properties` private.

## App Identity

Use these values in Google Play Console:

```text
App name: Sana-Chan
Package name / application ID: com.baytae.sanachan
Current Android versionCode: 42027
Current Android versionName: 4.2.27
Current Android target API: 35
Default launch command inside Discord: /sdac
Deep link scheme: sanachan://login-complete
```

Package names are permanent in Play Console. Create the app with `com.baytae.sanachan` only if you are sure this is the final package ID.

## Files Needed For Google Play

Required upload file:

```text
app-release.aab
```

This must be a release-signed Android App Bundle.

Useful local verification file:

```text
app-release.aab.sha256
```

Do not upload the debug APK to Google Play production. The debug APK is only for sideload testing.

## Signing Files Needed

You need a private upload keystore. Keep these private and do not commit them:

```text
keystore file: C:\Users\YOUR_USER\.sana-chan\android-signing\sanachan-upload.jks
keystore properties: apps/sdac-official-app/android/keystore.properties
```

Example `keystore.properties`:

```properties
storeFile=C:\Users\YOUR_USER\.sana-chan\android-signing\sanachan-upload.jks
storePassword=YOUR_STORE_PASSWORD
keyAlias=sanachan
keyPassword=YOUR_KEY_PASSWORD
```

Recommended key generation command:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.sana-chan\android-signing"
keytool -genkeypair `
  -v `
  -keystore "$env:USERPROFILE\.sana-chan\android-signing\sanachan-upload.jks" `
  -alias sanachan `
  -keyalg RSA `
  -keysize 4096 `
  -validity 10000
```

Keep the passwords somewhere safe. Losing the upload key/password can block future app updates until Google resets your upload key.

The Android project reads `apps/sdac-official-app/android/keystore.properties` automatically during `bundleRelease`. That file is ignored by git and should never be committed.

## Build Commands

From the app folder:

```powershell
cd D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit\apps\sdac-official-app
npm run build
npm run android:sync
```

Then build the release bundle:

```powershell
cd D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit\apps\sdac-official-app\android
$env:JAVA_HOME='C:\Program Files\Java\jdk-21.0.11'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat bundleRelease
```

Verify the signed bundle:

```powershell
jarsigner -verify -verbose -certs app\build\outputs\bundle\release\app-release.aab
Get-FileHash -Algorithm SHA256 app\build\outputs\bundle\release\app-release.aab
```

## Deobfuscation File

No deobfuscation file is required for the current release bundle because `minifyEnabled false` is set for the Android release build. If R8/ProGuard minification is enabled later, upload the generated mapping file with that release.

## Store Listing Items Needed

Prepare these before submitting:

- App name: Sana-Chan
- Short description, max 80 characters
- Full description, max 4000 characters
- App icon
- Feature graphic
- Phone screenshots
- Optional promo video / YouTube URL
- App category
- Tags
- Support email
- Support website, recommended
- Privacy policy URL

## Policy Forms Needed

Complete these in Play Console:

- Data Safety form
- Content rating questionnaire
- Target audience and children policy
- Ads declaration
- App access instructions, if reviewers need login access
- Data deletion instructions, if account data is collected
- Sensitive permissions declarations, if Play Console asks

## Testing Requirements

If this is a newer personal Google Play developer account, Google may require a closed test before production access. Be ready to set up:

- Closed testing track
- At least 12 opted-in testers
- Continuous testing period required by Play Console
- Tester instructions for login and core dashboard use

## Recommended First Release Path

1. Upload the signed `.aab` to Internal testing first.
2. Install from Play internal testing and verify Discord login, dashboard loading, app update panel, Invite Bot, and submissions.
3. Move to Closed testing if required.
4. Request production access after testing requirements are met.

## Current Blocker

No local signing blocker remains. The next blocker is Play Console readiness: upload the signed AAB to Internal testing and complete the required store listing, policy, and testing forms.