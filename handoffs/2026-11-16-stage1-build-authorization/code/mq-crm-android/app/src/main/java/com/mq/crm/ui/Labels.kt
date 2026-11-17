package com.mq.crm.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.mq.crm.R

/** Server values -> localized labels; anything unknown is shown as sent. */
@Composable
fun statusLabel(s: String): String = when (s) {
    "held" -> stringResource(R.string.status_held)
    "draft" -> stringResource(R.string.status_draft)
    "approved" -> stringResource(R.string.status_approved)
    "sent" -> stringResource(R.string.status_sent)
    "withdrawn" -> stringResource(R.string.status_withdrawn)
    "received" -> stringResource(R.string.status_received)
    else -> s
}

@Composable
fun purposeLabel(p: String?): String = when (p) {
    null -> stringResource(R.string.purpose_unset)
    "marketing" -> stringResource(R.string.purpose_marketing)
    "transactional" -> stringResource(R.string.purpose_transactional)
    "opt_out_confirmation" -> stringResource(R.string.purpose_confirmation)
    else -> p
}

@Composable
fun holdLabel(h: String?): String? = when (h) {
    null -> null
    "purpose_unclear" -> stringResource(R.string.hold_unclear)
    "promotional_content_in_transactional" -> stringResource(R.string.hold_promo)
    else -> h
}
