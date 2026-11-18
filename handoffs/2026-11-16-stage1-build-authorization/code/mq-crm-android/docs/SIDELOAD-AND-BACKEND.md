# Sideloading the TEST-ONLY APK, and what backend it needs

This APK is **TEST-ONLY** and **debug-signed**. It isn't on the Play Store and
shouldn't be. Use synthetic data only.

## 1. Get the APK onto the phone

The file is `app-debug.apk` (built by `./gradlew assembleDebug`, or provided by
engineering alongside the PR; it is **not** committed to git).

Pick one way to transfer it:
- **USB cable**: connect the phone, choose "File transfer", and copy the APK to `Download/`.
- **adb** (if developer options are on): `adb install app-debug.apk`.
- **Google Drive / email to yourself**: upload the file, then open it on the phone.

## 2. Allow installs from this source ("unknown sources")

On Android 8+ the permission is per app:
1. Open the APK from Files, Drive, or Chrome.
2. Android says it can't install apps from this source. Tap **Settings**.
3. Turn on **Allow from this source** for that app (Files, Drive or Chrome), then go back.
4. Tap **Install**.

Afterwards you can turn that permission off again in
Settings → Apps → Special app access → Install unknown apps.

## 3. Play Protect warning

Google Play Protect may show **"Unsafe app blocked"** or **"App scanned / unknown
developer"** because the app is debug-signed and not from the Play Store.
This is expected for this test build. Tap **More details → Install anyway**
(the wording varies by phone). Only do this for an APK you got directly from
our engineering team; check the SHA-256 in the PR if you want to be sure.

## 4. Uninstall

Settings → Apps → **M&Q CRM** → Uninstall (or long-press the icon → Uninstall).

## 5. The backend: what the phone needs to connect to

The app is only a client. It needs a running CRM backend at a URL the phone can reach.

- The backend must be the **PR #3 real-login backend** (it has `/api/auth/login`,
  `/me`, `/logout`). Create the first owner with
  `python -m app.auth_cli create-owner --username <name> --password-stdin`
  (no default password), then add staff/viewer users as that owner.
- **v0.3.1 server URL rule.** The app requires an `https://` server URL.
  In debug builds only, plain `http://` is accepted for `10.0.2.2`,
  `localhost`, and `127.0.0.1`. A LAN address such as
  `http://<laptop-ip>:8000` is refused, including in the debug build.
- `http://10.0.2.2:8000` (the debug default) works **only on the Android
  emulator**. It is the emulator's alias for the host's `127.0.0.1`, so run the
  backend on the host with `--host 127.0.0.1 --port 8000`. Don't type
  `localhost` in the emulator: that is the emulator itself. On a real phone
  `10.0.2.2` goes nowhere.
- A real phone needs an **`https://` address it can reach**, seeded with
  synthetic data. The usual path is the HTTPS tunnel URL the test-server pack
  prints at start (and saves in `TUNNEL_URL.txt`), for example
  `https://….trycloudflare.com` or the `https://….lhr.life` backup. Enter that
  address in Settings → Backend URL (or the Server field), then tap
  **Test connection**. Do not look up the computer's LAN IP.
- **Hosting a longer-lived server is a separate approval. Nothing has been
  hosted.** Any hosted or tunneled server must be HTTPS and the PR #3 backend.
- **The app has no TOTP (6-digit code) screen yet.** After owner two-step
  login is turned on, the owner account can sign in on the web only. Phone
  tests should use a staff account created with `add-staff`.

## 6. What "TEST-ONLY" means here

- The red banner on every screen and the `-TEST-ONLY-debug` version suffix.
- Real login (PR #3 backend); the role comes from the server. Still synthetic data only.
- Portuguese and Haitian Creole strings are pending native-speaker review.
- Debug signing: the certificate is `CN=Android Debug`, which isn't a release identity.
- Cleartext HTTP is allowed in this debug build only, and only for
  `10.0.2.2`, `localhost`, and `127.0.0.1` (emulator or same-device tests).
