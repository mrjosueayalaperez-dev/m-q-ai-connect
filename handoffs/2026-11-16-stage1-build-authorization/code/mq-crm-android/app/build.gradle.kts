plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Short commit SHA of the tree this APK was built from, shown in Settings so a
// screenshot / APK can be tied to an exact commit. "-dirty" if the app sources
// had uncommitted changes at build time; "unknown" outside a git checkout.
fun gitOut(vararg args: String): String = try {
    val p = ProcessBuilder("git", *args).directory(rootDir).redirectErrorStream(true).start()
    val out = p.inputStream.bufferedReader().readText().trim()
    if (p.waitFor() == 0) out else ""
} catch (e: Exception) { "" }
val gitSha: String = gitOut("rev-parse", "--short=7", "HEAD").ifEmpty { "unknown" } +
    (if (gitOut("status", "--porcelain", "--", ".").isNotEmpty()) "-dirty" else "")

android {
    namespace = "com.mq.crm"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.mq.crm"
        minSdk = 26
        targetSdk = 34
        versionCode = 4
        versionName = "0.3.1"
        // Empty by default: the operator types the backend URL in Settings.
        buildConfigField("String", "DEFAULT_BASE_URL", "\"\"")
        // Real login (bearer token from the PR #3 backend) is in place, but this
        // is still a debug-signed test build for synthetic data: TEST-ONLY.
        buildConfigField("boolean", "TEST_ONLY", "true")
        buildConfigField("String", "GIT_SHA", "\"$gitSha\"")
        // All four are selectable. PT/HT strings are complete but pending
        // native-speaker review (labelled in the app and the README).
        resourceConfigurations += listOf("en", "es", "pt", "ht")
    }

    buildTypes {
        debug {
            // Emulator loopback to the host's local CRM backend (tests only).
            buildConfigField("String", "DEFAULT_BASE_URL", "\"http://10.0.2.2:8000\"")
            versionNameSuffix = "-TEST-ONLY-debug"
            // Signed with the SDK's per-machine debug key (~/.android/debug.keystore),
            // which is outside this repository. No release signing config exists.
        }
        release {
            isMinifyEnabled = false
            versionNameSuffix = "-TEST-ONLY"
            // Intentionally NO signingConfig: release builds are unsigned and
            // not distributable. Release signing is a separate future approval.
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core") // v0.3.0 nav icons (BOM-managed, bundled)
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
