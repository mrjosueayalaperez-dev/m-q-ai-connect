"""Hardening (2026-11-18, review L6): request-validation errors (422)
without the caller's input.

FastAPI's default 422 body copies the submitted value ("input") and parser
context ("ctx", e.g. the JSON decoder message) back to the caller, which can
reflect a password or other private text into logs, proxies and screens.
This handler keeps the shape clients rely on (status 422, "detail" is a
list) and, per item, only:
  loc   where the problem is (body / query / path / header + field names or
        list indexes; anything that isn't a plain field name becomes "*")
  type  pydantic's stable error code, e.g. "missing", "int_parsing"
  msg   a fixed English sentence chosen by type (never pydantic's text)
Like other validation lists, it isn't translated (docs/ERROR-LANGUAGES.md);
"type" is the stable value to localize on.
"""
from __future__ import annotations

import re

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_TYPE = re.compile(r"^[a-z_]{1,64}$")
_ROOTS = {"body", "query", "path", "header", "cookie"}
_MAX_ITEMS = 50

MESSAGES = {
    "missing": "field required",
    "json_invalid": "request body is not valid JSON",
    "json_type": "request body must be JSON",
    "model_attributes_type": "must be a JSON object",
    "dict_type": "must be a JSON object",
    "list_type": "must be a list",
    "string_type": "must be a string",
    "int_type": "must be a whole number",
    "int_parsing": "must be a whole number",
    "int_from_float": "must be a whole number",
    "float_type": "must be a number",
    "float_parsing": "must be a number",
    "bool_type": "must be true or false",
    "bool_parsing": "must be true or false",
    "extra_forbidden": "field not allowed",
    "string_too_short": "too short",
    "string_too_long": "too long",
    "too_short": "too few items",
    "too_long": "too many items",
    "literal_error": "not one of the allowed values",
    "enum": "not one of the allowed values",
}
GENERIC = "invalid value"


def _loc(loc) -> list:
    out = []
    for i, part in enumerate(loc or ()):
        if isinstance(part, bool):
            out.append("*")
        elif isinstance(part, int):
            out.append(part)
        elif isinstance(part, str) and (part in _ROOTS if i == 0 else _FIELD.match(part)):
            out.append(part)
        else:
            out.append("*")
    return out[:10]


def sanitize(errors) -> list[dict]:
    items = []
    for e in list(errors or [])[:_MAX_ITEMS]:
        t = e.get("type") if isinstance(e, dict) else None
        t = t if isinstance(t, str) and _TYPE.match(t) else "invalid"
        items.append({"loc": _loc(e.get("loc") if isinstance(e, dict) else None),
                      "type": t, "msg": MESSAGES.get(t, GENERIC)})
    return items


async def handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse({"detail": sanitize(exc.errors())}, status_code=422)
