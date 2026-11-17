package com.mq.crm.ui

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.mq.crm.auth.AuthProvider
import com.mq.crm.auth.TestHeaderAuthProvider
import com.mq.crm.data.ApiClient
import com.mq.crm.data.Format
import com.mq.crm.data.Settings
import java.util.Locale

class MainActivity : ComponentActivity() {

    override fun attachBaseContext(newBase: Context) {
        // In-app EN/ES switch: the stored choice overrides the device locale.
        val lang = Settings(newBase).language.takeIf { it in Settings.ENABLED_LANGUAGES } ?: "en"
        val config = Configuration(newBase.resources.configuration)
        config.setLocale(Locale(lang))
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settings = Settings(this)
        setContent {
            MQTheme {
                CrmApp(
                    settings = settings,
                    authFor = { authFrom(settings) },
                    clientFor = { clientFrom(settings) },
                    onLanguageChanged = { recreate() },
                )
            }
        }
    }

    companion object {
        /** Today: TEST-ONLY self-asserted headers. Real login replaces this. */
        fun authFrom(s: Settings): AuthProvider = TestHeaderAuthProvider(s.role, s.actor)

        fun clientFrom(s: Settings): ApiClient? =
            Format.normalizeBaseUrl(s.baseUrl)?.let { ApiClient(it, authFrom(s)) }
    }
}
