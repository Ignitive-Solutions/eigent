# Building Eigent in Cloud Proxy Mode

Targets **eigent-dev.ignitive.ai** (cloud backend, no local Python backend bundled).

## Prerequisites

- Node.js >= 18 < 23 and npm
- macOS: Xcode Command Line Tools (code-signing)
- Windows cross-compile from macOS/Linux: Wine + mono (native Windows recommended)

## Environment

`.env.production` is pre-configured — no edits needed:

```
VITE_BASE_URL=https://eigent-dev.ignitive.ai/api
VITE_USE_LOCAL_PROXY=false
VITE_PROXY_URL=https://eigent-dev.ignitive.ai
```

Do **not** modify `.env.development` (preserves local desktop dev workflow).

## Install & Build

```bash
npm install
```

| Target | Command | Output in `release/` |
|--------|---------|----------------------|
| macOS | `npm run build:mac` | `Eigent-<ver>.dmg`, `Eigent-<ver>-mac.zip` |
| Windows | `npm run build:win` | `Eigent.Setup.<ver>.exe` |
| All platforms | `npm run build:all` | all of the above + Linux AppImage |

## Notes

- The built app routes all API calls to `https://eigent-dev.ignitive.ai`.
- The local Python backend is **not** bundled; `VITE_USE_LOCAL_PROXY=false` enables proxy routing.
- Auto-updater uses the `-mac.zip` archive; the `.dmg` is the user-facing installer.
