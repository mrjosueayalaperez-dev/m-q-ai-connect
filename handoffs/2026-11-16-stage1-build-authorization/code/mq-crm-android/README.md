# M&Q CRM — Android app (TEST-ONLY)

> **TEST-ONLY BUILD.** Real username/password login against the CRM backend
> from **PR #3** (`feat/crm-real-login-2026-11-17`). The app **requires that
> backend**: the older header-trusting backend (PR #1) has no `/api/auth/*`
> endpoints. Use only with synthetic data on a test backend. TEST-ONLY is
> shown three ways: an in-app banner on every screen (v0.3.0: a gold "TEST-ONLY
> BUILD" chip in the top bar), the version suffix (`0.3.0-TEST-ONLY-debug`), and this README.

Status: IMPLEMENTED / TESTED on an emulator against a local PR #3 backend.
Not merged, not deployed, not hosted, not on any store.

## What it is

A native Android app (Kotlin + Jetpack Compose, no WebView) for the same
FastAPI CRM backend in `../mq-crm` (+ batch overlays, including Batch 009 =
real login). It calls the existing JSON API at a configurable base URL.

| Screen | What it does |
|---|---|
| Sign in | Username + password (black and gold). Language picker and backend URL are reachable before sign-in |
| Customers | List; detail with contact permissions (marketing consent, per-channel opt-outs, retained do-not-message state) and the customer's messages |
| Message actions | held → release with a reason or re-classify; draft → approve; approved → send; sent → dispatch; withdraw. Shown only when the server says the signed-in user is owner/staff. Every refusal shows the server's reason verbatim |
| Approvals | Queue of held + draft messages; count of opt-out confirmations waiting for a human |
| Summary | KPIs straight from `/api/summary`; shows **—** when there is no data (no invented numbers). Owner-only suppression-key status and suppression list |
| Settings | Signed-in account (from the server), Sign out, backend URL, language, Test connection, build id (version + commit) |

No trading, broker or market features. The app never makes policy decisions
itself: consent, opt-outs, the do-not-message list, promo holds **and role
permissions** are enforced by the backend.

## Login and sessions (Batch 009 client)

- `POST /api/auth/login` with `{"username","password","mode":"token"}` →
  bearer token. Every later request sends only `Authorization: Bearer …`.
- **Role and display name come only from `GET /api/auth/me`.** The app hides
  buttons the role can't use, but that is cosmetic: the server enforces.
- **No `X-Role` / `X-Actor` headers, ever.** The request interceptor
  (`ApiClient.headersFor`) strips them even if a provider tried to add them.
  The role picker and the editable audit name are gone; legacy prefs are deleted.
- **Token at rest:** encrypted with AES-256-GCM under a non-exportable key in
  the **AndroidKeyStore** (alias `mq_crm_session_token_key`), stored as
  `v1:<iv>:<ciphertext>` in private SharedPreferences. An unreadable or
  tampered value is dropped (treated as signed out). `allowBackup=false`.
- **Logout:** `POST /api/auth/logout` (server revokes the token), then the
  local token is **always** cleared, even if the server call fails by network
  error, timeout or error status.
- **Any 401** (expired, revoked, idle) clears the token and returns to the
  sign-in screen. A 401 on the login call itself is just "wrong password".
- Passwords and tokens are never logged (the app has no logging calls), never
  shown, and the password field is cleared after each attempt.
- Changing the backend URL signs out first (the session belongs to the old server).

## Languages

All four are selectable in Settings and on the sign-in screen.

- **EN**: source. **ES**: complete, reviewed by the builder only.
- **PT** and **HT**: complete strings, but **pending native-speaker review**.
  Settings shows a visible "pending native review" note when either is
  selected. Don't treat them as validated.

## Build ($0 tooling)

Requirements: JDK 17 and the Android SDK (platform 34, build-tools 34.0.0).

```bash
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk   # or write sdk.dir in local.properties (git-ignored)
./gradlew clean assembleDebug testDebugUnitTest
# -> app/build/outputs/apk/debug/app-debug.apk
```

The build embeds the short git SHA (`BuildConfig.GIT_SHA`, `-dirty` if the
app sources had uncommitted changes); Settings shows `v<version> · <sha>`.

Stack: Gradle 8.7 wrapper, AGP 8.5.2, Kotlin 1.9.24, Compose BOM 2024.06.00,
minSdk 26, targetSdk 34. HTTP uses `HttpURLConnection` + `org.json` behind a
small `HttpTransport` interface (faked in unit tests).

## Signing

- **Debug signing only** with the build machine's `~/.android/debug.keystore`,
  which stays **outside this repo** and is not a release identity.
- **No release keystore exists.** `.gitignore` blocks `*.jks`, `*.keystore`,
  `keystore.properties` and `signing.properties`.

## Network / cleartext

- `src/main/res/xml/network_security_config.xml`: **cleartext disabled** (HTTPS only).
- `src/debug/res/xml/network_security_config.xml`: cleartext allowed **in
  debug builds only**, and only for `10.0.2.2`, `localhost`, and `127.0.0.1`.
  Anything else, including a LAN IP or a hosted name, must be HTTPS.
- **Emulator → local backend:** run the PR #3 backend on the host at
  `127.0.0.1:8000`; inside the emulator use **`http://10.0.2.2:8000`** (the
  emulator's alias for the host loopback). `localhost`/`127.0.0.1` inside the
  emulator is the emulator itself and will not work. The debug build defaults
  to `http://10.0.2.2:8000`; release has no default.
- The only permission is `INTERNET`.

## Server URL and two-step login (v0.3.1)

The app requires an `https://` server URL. In debug builds only, plain `http://`
is accepted for `10.0.2.2`, `localhost`, and `127.0.0.1`. A phone on the LAN
cannot use `http://<laptop-ip>` — that URL is refused. A real phone needs an
`https://` address it can reach (for example a temporary tunnel URL).

The app has **no TOTP (6-digit code) screen yet**. After owner two-step login
is turned on, the owner account can sign in on the web only. Phone tests should
use a staff account created with `add-staff` (see the test-server pack).

## Tests

`./gradlew testDebugUnitTest` runs JVM unit tests:
- `AuthTest`: token store round trip (ciphertext only at rest), fresh IV,
  tamper/wrong-key rejection, the interceptor never sends role/actor headers,
  only the bearer is sent, login → role from `/me`, wrong password (no store,
  no sign-out), any 401 clears and signs out, restore after restart, logout
  revokes then clears, logout clears even on network error / timeout / 5xx /
  401, `Me` parsing.
- `CoreLogicTest`: "—" no-data formatting, base-URL validation, all four
  languages selectable with PT/HT flagged pending review, TEST-ONLY build flag.
- `ThemeTest` (v0.3.0): palette values match the web dashboard tokens, WCAG AA
  text contrast on every background, 3:1 input outlines, gold-button text,
  same string keys in all four languages, TEST-ONLY label present in each.

## Look (v0.3.0)

Black-and-gold, matching the web sign-in and dashboard (Batch 009c/009d):
`ui/BrandPalette.kt` holds the same colour values as `web/styles.css`, and
`ui/Theme.kt` maps them to Material 3 (system font, web weights, rounded cards).
Sign-in: MQ monogram, M&Q CRM wordmark, gold-bordered card, gold button.
Summary: a gold highlight card for Payments received plus KPI tiles (the same six
backend figures; "—" when there is no data). Nav bar uses outlined icons.
Presentation only: no auth, session, token or network change.

## Installing on a phone

See [docs/SIDELOAD-AND-BACKEND.md](docs/SIDELOAD-AND-BACKEND.md).
