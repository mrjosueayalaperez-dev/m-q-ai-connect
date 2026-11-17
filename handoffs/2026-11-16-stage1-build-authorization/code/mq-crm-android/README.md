# M&Q CRM — Android app (TEST-ONLY)

> **TEST-ONLY BUILD.** No real login: the role (owner / staff / viewer) is
> self-asserted in Settings and sent as `X-Role` / `X-Actor` headers, which the
> CRM backend currently trusts. Use only with synthetic data on a test backend.
> The TEST-ONLY status is shown three ways: a red in-app banner on every screen,
> the version suffix (`0.1.0-TEST-ONLY-debug`), and this README.

Status: IMPLEMENTED / TESTED on an emulator. Not merged, not deployed, not on
any store.

## What it is

A native Android app (Kotlin + Jetpack Compose, no WebView) for the same
FastAPI CRM backend in `../mq-crm` (+ batch overlays). It calls the existing
JSON API at a configurable base URL.

| Screen | What it does |
|---|---|
| Customers | List; detail with contact permissions (marketing consent, per-channel opt-outs, retained do-not-message state) and the customer's messages |
| Message actions | held → release with a reason or re-classify; draft → approve; approved → send; sent → dispatch; withdraw. Shown only to owner/staff. Every refusal shows the server's reason verbatim |
| Approvals | Queue of held + draft messages; count of opt-out confirmations waiting for a human |
| Summary | KPIs straight from `/api/summary`; shows **—** when there is no data (no invented numbers). Owner-only suppression-key status and suppression list |
| Settings | Backend URL, role, name (audit log), language, Test connection |

No trading, broker or market features.

The app never makes policy decisions itself: consent, opt-outs, the
do-not-message list and promo holds are enforced by the backend at send and
dispatch, and the app just displays what the backend allows or refuses.

## Languages

- **EN** and **ES**: complete; switch in Settings (applies immediately).
  The Spanish strings were reviewed by the builder only, not by a native-speaker reviewer.
- **PT** and **HT**: planned for in the architecture (`values-pt`, `values-ht`,
  locale config) but **pending native-speaker validation**. They are disabled in
  Settings and fall back to English. Do not enable them until a native speaker
  approves the translations.

## Build ($0 tooling)

Requirements: JDK 17 and the Android SDK (platform 34, build-tools 34.0.0).

```bash
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk   # or write sdk.dir in local.properties (git-ignored)
./gradlew assembleDebug testDebugUnitTest
# -> app/build/outputs/apk/debug/app-debug.apk
```

Stack: Gradle 8.7 wrapper, AGP 8.5.2, Kotlin 1.9.24, Compose BOM 2024.06.00,
minSdk 26, targetSdk 34. HTTP uses `HttpURLConnection` + `org.json`, so there
are no extra network libraries.

## Signing

- **Debug signing only.** Gradle signs debug builds with the standard
  `~/.android/debug.keystore`. That file is generated on the build machine,
  stays **outside this repo**, and is not a release identity.
- **No release keystore exists.** The release build type has no signing config.
  `.gitignore` blocks `*.jks`, `*.keystore`, `keystore.properties` and
  `signing.properties`.
- A release or Play Store build needs a separate approval and a properly managed key.

## Network / cleartext

- `src/main/res/xml/network_security_config.xml`: **cleartext disabled** (HTTPS only).
- `src/debug/res/xml/network_security_config.xml`: cleartext allowed **in
  debug builds only**, so the emulator can reach a local backend at
  `http://10.0.2.2:8000`. The debug build defaults to that URL; release has no default.
- `allowBackup=false` and data-extraction rules exclude app data from backups.
- The only permission is `INTERNET`.

## Auth plug-in point

`auth/AuthProvider.kt` defines the `AuthProvider` interface (`headers()`,
`isTestOnly`, `role`, `displayName`). `TestHeaderAuthProvider` is the
TEST-ONLY implementation. Real login (session or token from the backend) will be a
new implementation; the screens and `ApiClient` won't change. Real-login work
has **not** started and needs Josue's approval.

## Tests

`./gradlew testDebugUnitTest` runs the JVM unit tests (`CoreLogicTest`): the
"—" no-data formatting, base-URL validation, test-auth headers and role
gating, and language enablement.

## Installing on a phone

See [docs/SIDELOAD-AND-BACKEND.md](docs/SIDELOAD-AND-BACKEND.md).
