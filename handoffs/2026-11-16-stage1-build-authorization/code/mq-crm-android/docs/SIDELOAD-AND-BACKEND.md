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

- `http://10.0.2.2:8000` (the debug default) works **only on the Android
  emulator**. It means "the computer running the emulator". On a real phone it
  goes nowhere.
- A real phone needs a **hosted test server with HTTPS** (e.g.
  `https://crm-test.example.com`), seeded with synthetic data. Enter it in
  Settings → Backend URL, then tap **Test connection**.
- **Hosting that server is a separate approval. Nothing has been hosted.**
  Before hosting, the test server also needs real login, because today
  anyone who can reach the backend can claim the owner role.
- Optional LAN-only test (debug build, no hosting): run the backend on a laptop
  bound to its LAN IP and enter `http://<laptop-ip>:8000` on a phone on the same
  Wi-Fi. Plain HTTP works only because this is a debug build. Use it only
  briefly on a trusted network, with synthetic data.

## 6. What "TEST-ONLY" means here

- The red banner on every screen and the `-TEST-ONLY-debug` version suffix.
- The role you choose in Settings is **self-asserted**. There is no real login yet.
- Debug signing: the certificate is `CN=Android Debug`, which isn't a release identity.
- Cleartext HTTP is allowed in this debug build only.
