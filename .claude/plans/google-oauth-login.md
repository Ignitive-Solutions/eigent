# Google OAuth Login for Cloud Mode

## Context

The Login page in cloud mode redirects to `eigent.ai/signin` for Google auth. After Google login, the user gets a token from **their** server, not yours. Your server has no Google OAuth login endpoint — only email/password (`/api/v1/user/login`) and integration OAuth (no user creation). Need a "login with Google" flow that creates/finds a user on YOUR server and returns YOUR JWT.

## Approach

Create a new server endpoint `/api/v1/user/google-login` that takes a Google OAuth authorization code, exchanges it for user info, finds or creates the user, and returns a JWT. Then wire the Electron login button to use this flow.

## Changes

### 1. `server/app/domains/user/api/login_controller.py` — Add Google OAuth login endpoint

New endpoint: `POST /api/v1/user/google-login`
```python
class GoogleLoginIn(BaseModel):
    code: str

@router.post("/google-login")
async def google_login(data: GoogleLoginIn, db_session: Session = Depends(session)):
    # 1. Exchange code for Google tokens using GoogleSuiteOAuthAdapter
    # 2. Fetch user profile from Google (email, name, picture)
    # 3. Find or create user in DB
    # 4. Return JWT
```

Uses existing:
- `GoogleSuiteOAuthAdapter` from `server/app/core/oauth_adapter.py` — already exchanges codes for tokens
- Google userinfo endpoint `https://www.googleapis.com/oauth2/v2/userinfo`
- `User` model from `server/app/model/user/user.py`
- `create_access_token` from `server/app/shared/auth/`

Need a **separate** Google OAuth client ID/secret for login (not the `googlesuite` one which has Drive scopes). Add env vars:
- `GOOGLE_LOGIN_CLIENT_ID`
- `GOOGLE_LOGIN_CLIENT_SECRET`

Or reuse `GOOGLE_SUITE_CLIENT_ID`/`SECRET` if the user prefers (they might be the same Google project).

### 2. `server/.env.example` + `server/.env` — Add Google login env vars

```
GOOGLE_LOGIN_CLIENT_ID=your-google-login-client-id
GOOGLE_LOGIN_CLIENT_SECRET=your-google-login-client-secret
```

### 3. `electron/main/index.ts` — Handle OAuth callback for login

The existing `processProtocolUrl` (line 475) already handles `eigent://callback/oauth?provider=...&code=...` and sends `oauth-authorized` IPC. No change needed here.

### 4. `src/pages/Login.tsx` — Wire login button to your server's OAuth flow

**Cloud mode login button** (line 352-358): Change from opening `eigent.ai/signin` to opening your server's `/api/v1/oauth/googlesuite/login`. But this needs a separate adapter with login-appropriate redirect URI...

Actually simpler approach: use a **new** server endpoint for the login redirect:

### 1a. `server/app/domains/user/api/login_controller.py` — Add Google auth redirect + callback

```
GET  /api/v1/user/google-auth     → redirects to Google login
GET  /api/v1/user/google-callback → exchanges code, creates user, redirects to eigent://callback/oauth
```

The callback endpoint:
1. Receives `code` from Google
2. Exchanges for token + userinfo
3. Finds/creates user
4. Generates JWT
5. Redirects to `eigent://callback/oauth?provider=google&code={jwt_token}`

Wait — that's overloading `code`. Better: redirect to `eigent://auth/callback?token={jwt}` which the existing `authCallbackServer` (line 550-589) already handles — it sends `auth-token-received` IPC with the token.

Then in Login.tsx, the existing `auth-token-received` handler (line 217) already:
1. Receives token
2. Calls `proxyFetchGet('/api/v1/user')` with the token
3. Gets user info
4. Sets auth state

That's perfect — no changes needed in Login.tsx!

### Revised plan:

#### Server: 2 new endpoints

**`GET /api/v1/user/google-auth`** — Redirects to Google OAuth
- Uses `GOOGLE_LOGIN_CLIENT_ID` + `GOOGLE_LOGIN_SECRET`
- `redirect_uri` = `{server_url}/api/v1/user/google-callback`
- `scope` = `openid email profile` (no Drive scope needed)

**`GET /api/v1/user/google-callback`** — Exchanges code, creates user, redirects to Electron
1. Exchange `code` for Google token
2. Fetch userinfo from `https://www.googleapis.com/oauth2/v2/userinfo`
3. Find user by email, or create new user
4. Create JWT via `create_access_token(user.id)`
5. Redirect to `eigent://auth/callback?token={jwt}`
6. Electron's `authCallbackServer` catches this → sends `auth-token-received` IPC
7. Login.tsx's existing handler sets auth state

#### Frontend: 1 line change in Login.tsx

Line 355: Change login URL from `eigent.ai/signin?callbackUrl=...` to `{proxy_url}/api/v1/user/google-auth`

#### Server env: Add Google login credentials

`GOOGLE_LOGIN_CLIENT_ID` + `GOOGLE_LOGIN_CLIENT_SECRET` in `.env`

## Files to modify

| File | Change |
|------|--------|
| `server/app/domains/user/api/login_controller.py` | Add `GET /google-auth` + `GET /google-callback` |
| `server/.env.example` | Add `GOOGLE_LOGIN_CLIENT_ID` / `GOOGLE_LOGIN_CLIENT_SECRET` |
| `src/pages/Login.tsx` | Change login button URL in cloud mode to use your server |

## Verification

1. Set `GOOGLE_LOGIN_CLIENT_ID` and `GOOGLE_LOGIN_CLIENT_SECRET` in `server/.env`
2. Restart server
3. In Electron app, click "Log in" → should open Google login
4. After Google auth, browser redirects to `eigent://auth/callback?token=...`
5. Electron catches protocol → sends token to renderer → user is logged in
