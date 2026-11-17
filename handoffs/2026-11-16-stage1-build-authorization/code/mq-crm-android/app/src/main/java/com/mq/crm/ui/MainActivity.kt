package com.mq.crm.ui

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.mq.crm.auth.AesGcmCodec
import com.mq.crm.auth.AndroidKeystoreKey
import com.mq.crm.auth.EncryptedTokenStore
import com.mq.crm.auth.PrefsKeyValue
import com.mq.crm.auth.TokenStore
import com.mq.crm.data.Settings
import java.util.Locale

class MainActivity : ComponentActivity() {

    override fun attachBaseContext(newBase: Context) {
        // In-app language switch: the stored choice overrides the device locale.
        val lang = Settings(newBase).language.takeIf { it in Settings.LANGUAGES } ?: "en"
        val config = Configuration(newBase.resources.configuration)
        config.setLocale(Locale(lang))
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settings = Settings(this)
        val store = tokenStore(this)
        setContent {
            MQTheme {
                CrmApp(settings = settings, store = store, onLanguageChanged = { recreate() })
            }
        }
    }

    companion object {
        /** The bearer token, sealed with an AES-GCM key held in the Android Keystore. */
        fun tokenStore(context: Context): TokenStore =
            EncryptedTokenStore(PrefsKeyValue(context), AesGcmCodec { AndroidKeystoreKey.getOrCreate() })
    }
}
