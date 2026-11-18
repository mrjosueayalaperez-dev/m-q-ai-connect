# Server / API error messages in EN, ES, PT, HT (Batch 010b)

**PT (pt-BR) and HT (Kreyòl ayisyen) are pending native-speaker review.** ES should also
get a native read before release.

## What changes

For an `/api` error response (status 400 or higher) whose JSON body has a string
`detail`, the server sends `detail` in the caller's language:

```json
{"detail": "usuario o contraseña incorrectos", "detail_en": "invalid username or password"}
```

- The original English text is also returned in `detail_en`. It is a stable value for
  clients that compare strings; the web sign-in screen uses it.
- `Content-Language` and `Vary: Accept-Language, X-MQ-Lang` are added to translated responses.
- English responses are byte-for-byte unchanged.
- Request-validation errors (422, a list) are left as they are.
- A message with no catalog entry stays English.
- Values inside a message (statuses, names, file paths, env-var names) are codes and are not translated.

## Language choice (first match wins)

1. `?lang=es|pt|ht|en`
2. `X-MQ-Lang` header. The web UI sends its current language on every `api()` call.
3. `Accept-Language`, by q-value.
4. English.

## Security: unchanged

- **Same status codes** in every language. A test compares them across EN/ES/PT/HT.
- **Same headers:** `Retry-After` on lockout, `WWW-Authenticate` on 401, `Set-Cookie` flags
  (HttpOnly, Secure, SameSite=Strict, Path=/api). CSRF and Origin checks still return 403.
- **One generic sign-in failure per language.** Unknown user and wrong password return the
  identical body, so nothing reveals whether an account exists.
- Lockout limits and timing are unchanged. The forged `X-Role` header is still ignored (401).
- Implementation: `app/error_i18n.py`, an outermost ASGI middleware that rewrites only the
  `detail` text of error bodies. Tests: `tests/test_batch10b.py`. Its coverage test finds every
  literal error raised in `app/` and requires an ES, PT and HT entry for each.
