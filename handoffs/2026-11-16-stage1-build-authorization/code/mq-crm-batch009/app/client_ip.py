"""Hardening (2026-11-18, review L4): the client address used by the
per-address sign-in throttle.

Default (MQ_CRM_TRUSTED_PROXIES unset or empty): the direct TCP peer, and
X-Forwarded-For is IGNORED. Nobody can pick their own throttle bucket.

Opt-in: MQ_CRM_TRUSTED_PROXIES is a comma-separated list of IP addresses or
CIDR networks (e.g. "127.0.0.1" for a tunnel on the same machine, or
"10.0.0.0/8" for a hosting provider's load balancer). Only when the direct
peer is in that list is X-Forwarded-For read, and then right to left: the
first address that is NOT itself a trusted proxy is the client. Anything
malformed falls back to the direct peer. Forwarded / X-Real-IP are never read.

An invalid entry in the setting refuses startup (fail closed), so a typo
can't silently disable or widen the trust.

Note for operators: uvicorn applies ITS OWN proxy-header handling before the
app sees the request (by default it trusts X-Forwarded-For from 127.0.0.1).
Run it with --no-proxy-headers so this setting is the only place that decides.
"""
from __future__ import annotations

import ipaddress
import os

ENV = "MQ_CRM_TRUSTED_PROXIES"
_MAX_HOPS = 20


class TrustedProxyConfigError(ValueError):
    pass


def parse_trusted(value: str | None) -> tuple:
    nets = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            raise TrustedProxyConfigError(
                f"{ENV} has an entry that is not an IP address or CIDR network:"
                f" {part!r}") from None
    return tuple(nets)


TRUSTED = parse_trusted(os.environ.get(ENV))


def _ip(s: str):
    try:
        return ipaddress.ip_address(s.strip())
    except ValueError:
        return None


def _is_trusted(addr, trusted) -> bool:
    return addr is not None and any(addr.version == n.version and addr in n for n in trusted)


def resolve(peer: str | None, forwarded_for: list[str] | None, trusted=None) -> str:
    """The address to throttle on. `forwarded_for` is every X-Forwarded-For
    header value, in order."""
    trusted = TRUSTED if trusted is None else trusted
    peer = peer or "unknown"
    if not trusted or not forwarded_for or not _is_trusted(_ip(peer), trusted):
        return peer
    hops = [h.strip() for v in forwarded_for for h in v.split(",")]
    if not hops or len(hops) > _MAX_HOPS * 5:
        return peer
    for hop in reversed(hops[-_MAX_HOPS:]):
        addr = _ip(hop)
        if addr is None:
            return peer                      # malformed chain: don't guess
        if not _is_trusted(addr, trusted):
            return str(addr)
    return peer                              # every hop is a trusted proxy
