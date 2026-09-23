# AMD wheels status (Sep 2026)

## What worked, what's broken, and how the fork handles each

Last checked: 2026-09-23.

## URLs that work

The fork's catalog pins these wheels, downloaded successfully into the
user's `D:\GoKuk\cache\wheels\` during the September 22 install:

| Wheel | URL | SHA256 |
|---|---|---|
| torch 2.10.0+rocm7.12 cp312 | `https://rocm.nightlies.amd.com/v2/gfx120X-all/torch/torch-2.10.0%2Brocm7.12.0a20260311-cp312-cp312-win_amd64.whl` | `1fb488c6ab4e3496969b954c3591ac7782a21ed837af759d0bb816b8a84bff87` |
| torch 2.10.0+rocm7.12 cp311 | `…torch-2.10.0%2Brocm7.12.0a20260311-cp311-cp311-win_amd64.whl` | `078864ef744a630fea85e993e9defc8cdff697c6c65ea04558bb8bea469b33ed` |
| torchaudio 2.10.0+rocm7.12 cp312 | `…torchaudio-2.10.0%2Brocm7.12.0a20260311-cp312-cp312-win_amd64.whl` | `b495049166840a50468ee95d210d34e9d05e1e6081898614488d9cfede1a009f` |
| torchaudio 2.10.0+rocm7.12 cp311 | `…torchaudio-2.10.0%2Brocm7.12.0a20260311-cp311-cp311-win_amd64.whl` | `b7ac9af517d4712965ba28e3e8cebbe289ec3ef11ecce222a439e9bf8804b57e` |

These wheels have been preserved by the user's `D:\GoKuk\cache\wheels\` —
**as long as that directory is kept, the fork can re-install on top of a
clean state without re-downloading**.

## URLs that stopped working (Sep 2026)

All of these returned `404 NoSuchKey` or `403 AccessDenied` when probed
in September 2026:

| URL pattern | Status |
|---|---|
| `https://rocm.nightlies.amd.com/v2/gfx120X-all/torch/...` | 404 (even for the wheel that worked earlier) |
| `https://rocm.nightlies.amd.com/v2-staging/gfx120X-all/torch/...` | 404 (staging index also broken) |
| `https://rocm.nightlies.amd.com/whl-multi-arch/amd-torch-device-gfx1201/...` | 404 (per-arch format, all dates and builds) |
| `https://download.pytorch.org/whl/rocm7.0/torch/` | 200 OK index but **zero Windows wheels listed** |
| `https://download.pytorch.org/whl/rocm7.10/` | 403 AccessDenied |
| `https://download.pytorch.org/whl/rocm7.12/` | 403 AccessDenied |
| `https://download.pytorch.org/whl/rocm/` | 403 AccessDenied |

This means **AMD nightly for AMD's per-gfx ROCm Windows wheels is
functionally dead as a public-downloadable resource**. The HTML
indices still render and list wheels (the AMD server is alive), but
the actual wheel files return 404.

### Probable cause

This is consistent with AMD's planned transition to **TheRock-based
releases** (documented in commit history of
[ROCm/TheRock](https://github.com/ROCm/TheRock)). Phoronix coverage
of the ROCm 10.0 release noted: *"Windows will follow the same
release cadence as Linux for ROCm releases. Right now the ROCm Core
SDK for Windows is a simple static package while later in the year
they are working toward native Windows installer support."* The
multi-arch index at `whl-multi-arch/amd-torch-device-gfx*/` is the
preview of that future shape. Until AMD's S3 sync is fixed, these
indices list wheels that don't actually download.

## What the fork does about it

### Cache-based re-install

`setup/download.py` matches cached files against the catalog by size
and SHA256. Once a wheel is in `cache/wheels/`, subsequent installs
reuse it without going to the network. So:

1. The first install required network and worked (May 2026 / March
   2026 dates).
2. Subsequent installs with the cache present use them and never
   touch the network.
3. If `cache/wheels/` is deleted, the fork cannot re-download —
   the URLs all 404.

### Detection before download

If the cache is missing, `setup/download.py` will report
`WinError 10053 (or similar)` for the first wheel and `setup_steps.install_wheels`
will fail on the first PyTorch install. The fork does not currently
have a pre-check that distinguishes **404 file missing** from
**404 URL invalid**, because the URL response is opaque.

## Workarounds if the cache is lost

1. **Mirror the wheels locally**: download the working wheels on any
   machine that has network access, copy them into
   `cache/wheels/`. The fork's `verify_hashes.py` then accepts
   them on next install.
2. **Pull from a fork-specific mirror**: if you control a small web
   server, host the four wheels above and edit `catalog.json` to
   point at `https://your-server/wheels/{name}.whl`.
3. **Skip torch entirely**: use llama.cpp's GGUF quantization of YuE2
   (an alternative community effort, not in the fork).
4. **Use Linux**: AMD's Linux ROCm wheels are present and stable; run
   the fork on Linux instead of Windows.

## Wheel check command

```powershell
$urls = @(
    "https://rocm.nightlies.amd.com/v2/gfx120X-all/torch/torch-2.10.0%2Brocm7.12.0a20260311-cp312-cp312-win_amd64.whl"
    "https://rocm.nightlies.amd.com/whl-multi-arch/amd-torch-device-gfx1201/amd_torch_device_gfx1201-2.9.1%2Brocm7.15.0a20260715-cp312-cp312-win_amd64.whl"
    "https://download.pytorch.org/whl/rocm7.10/torch/"
)
foreach ($u in $urls) {
    $r = Invoke-WebRequest -Uri $u -Method HEAD -UseBasicParsing -ErrorAction SilentlyContinue
    Write-Host "$($r.StatusCode)  $($u)"
}
```

Expected output: at minimum `404` for any of the AMD nightly URLs and
either `403` or `404` for `download.pytorch.org/whl/rocm*`. If a wheel
URL gives `200`, the situation has changed for the better; rerun
`setup` and the cache will refresh.

## What this means for the fork's roadmap

| Item | Status |
|---|---|
| Phase 1 (source patches) | ✅ shipped, 66/66 tests pass |
| Phase 2 (catalog + Setup GUI) | ✅ shipped |
| Phase 2b (AMD wheel list) | ⚠️ shipped but URLs stale; cache-only re-install |
| Phase 2c (docs) | ✅ shipped |
| Phase 3 (PyInstaller DLL bundling) | ✅ shipped |
| Phase 4 (4-tier GPU detection) | ✅ shipped, verified live on RX 9070 XT |
| Phase 5 (smoke test on hardware) | ✅ shipped, reported in `docs/VALIDATION_RX_9070_XT.md` |
| Phase 5 fixes (1-5 + doc) | ✅ shipped (5 commits on top of Phase 5) |
| Phase 6 (HIP SDK shim) | ⚠️ in progress, blocked on Windows Defender / shm.dll stub |
| Phase 6 + sign / `rocm_sdk` wheel | ❌ awaiting AMD Windows wheel publication |

Until AMD publishes the `rocm_sdk_core` Python wheel for Windows and
fixes the S3 404s on the nightly index, the end-to-end song
generation on Windows is one blocked at:

* either the cache survives intact (current state — work continues)
* or a real network-installed backup is possible (next AMD release)

The fork's Phase 6 `_rocm_init.py` shim is the right shape for
working around `rocm_sdk` import once the cache is back online.

## If you are a fork maintainer reading this later

When AMD fixes the S3 issue:

1. Re-run the URL probe (PowerShell snippet above) to confirm
2. `git pull` the latest fork
3. `rm -rf cache/wheels cache/state`
4. `python GokukSetup.py` — setup re-downloads and installs
5. `python Gokuk.py` — run the fork normally

When AMD publishes the `rocm_sdk` Python wheel for Windows:

1. The `_rocm_init.py` shim can be reverted to the upstream version
2. The `rocm_sdk_core` and `rocm_sdk_libraries_gfx120x_all` entries
   in `setup/catalog.json` (commit `ca55536`) become reachable
3. `docs/AMD_WHEELS.md` should be updated to remove the "manual
   install" warning in § 3

Until either of those happens, the current fork state is the best
this project can do.