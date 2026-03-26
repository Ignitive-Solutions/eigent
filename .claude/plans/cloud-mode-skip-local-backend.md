# Cloud Mode: Skip Local Backend in Electron

## Context

The Electron app always installs Python deps (uv, bun, 190 pip packages) and spawns a local `uvicorn` backend. When `VITE_USE_LOCAL_PROXY=false` (cloud mode), this is unnecessary — auth, orchestration, and chat all route to the remote server. The app gets stuck on a carousel/install screen waiting for a local backend that will never be used and isn't needed.

## Approach

Add a cloud mode guard in **three places**:
1. **Electron main process** — skip `checkAndInstallDepsOnUpdate()` + `startBackendAfterInstall()`, send fake "ready" events instead
2. **Frontend hook** — `useInstallationSetup` immediately sets `initState='done'` and `isBackendReady=true` in cloud mode

This lets the Electron app launch, skip all local backend machinery, and show the login screen directly.

## Changes

### 1. `electron/main/init.ts` — Export `readEnvValue`

`readEnvValue` (line 45) is currently a private function. Export it so the main index can use it to read `.env.development`.

```diff
-function readEnvValue(filePath: string, key: string): string | undefined {
+export function readEnvValue(filePath: string, key: string): string | undefined {
```

### 2. `electron/main/index.ts` — Add `isCloudMode()` helper + guard the startup flow

**Import `readEnvValue`** (add to existing import from `./init`):
```typescript
import { checkToolInstalled, findAvailablePort, killProcessOnPort, startBackend, readEnvValue } from './init';
```

**Add helper** (after line 78, near other constants):
```typescript
const isCloudMode = (): boolean => {
  if (process.env.VITE_USE_LOCAL_PROXY === 'true') return false;
  const devEnvPath = path.join(MAIN_DIST, '.env.development');
  return readEnvValue(devEnvPath, 'VITE_USE_LOCAL_PROXY') !== 'true';
};
```

**Guard installation check** (~line 2996). Wrap the `needsInstallation` block:
```typescript
if (needsInstallation && !isCloudMode()) {
  // ... existing carousel injection logic
}
```

**Guard deps install + backend start** (~lines 3115-3142):
```typescript
if (isCloudMode()) {
  log.info('[CLOUD MODE] Skipping local backend — using remote server');
  if (win && !win.isDestroyed()) {
    win.webContents.send('install-dependencies-complete', { success: true, code: 0 });
    await new Promise((resolve) => setTimeout(resolve, 500));
    win.webContents.send('backend-ready', { success: true, port: 0 });
  }
  return;
}

// ... existing checkAndInstallDepsOnUpdate + startBackendAfterInstall
```

### 3. `src/hooks/useInstallationSetup.ts` — Cloud mode early return

In the mount useEffect (~line 164), add a cloud mode check at the top:
```typescript
const IS_CLOUD_MODE = import.meta.env.VITE_USE_LOCAL_PROXY !== 'true';

useEffect(() => {
  if (hasCheckedOnMount.current) return;
  hasCheckedOnMount.current = true;

  if (IS_CLOUD_MODE) {
    installationCompleted.current = true;
    backendReady.current = true;
    setSuccess();  // sets state='completed' + isBackendReady=true
    setInitState('done');
    return;
  }

  // ... existing tool check + IPC listener logic
}, []);
```

## Files to modify

| File | Change |
|------|--------|
| `electron/main/init.ts` | Export `readEnvValue` |
| `electron/main/index.ts` | Add `isCloudMode()`, guard install + backend startup |
| `src/hooks/useInstallationSetup.ts` | Cloud mode early return in mount effect |

## Verification

1. Ensure `.env.development` has `VITE_USE_LOCAL_PROXY=false` (already set)
2. Run `npm run dev` — Electron should launch WITHOUT installing Python deps
3. App should show login screen directly (no carousel/install screen)
4. Login → should work against the droplet's server (via VS Code port forwarding on 8001)
