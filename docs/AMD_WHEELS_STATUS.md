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

## ROCm 10.0 wheel architecture (per kpack discovery, Sep 2026)

A user-found wheel at `D:\amd_torch_device_gfx1201-2.10.0+rocm7.15.0a20260627-cp312-cp312-win_amd64.whl` exposed AMD's new multi-arch packaging model. Inspection:

* Wheel is **only a HIP kernel pack** (`.kpack` file format, magic `KPAK`).
* Wheel size: 48.2 MB (vs ~250 MB for old single-wheel `torch`).
* Contents: `torch/.kpack/torch_gfx1201.kpack` + METADATA + RECORD. No `__init__.py`, no `lib/*.dll`, no `_rocm_init.py`.
* `Requires-Dist` in METADATA:
  - `torch == 2.10.0+rocm7.15.0a20260627`
  - `rocm-sdk-device-gfx1201 == 7.15.0a20260627`

This means ROCm 10.0 PyTorch on Windows uses a **3-wheel split**:

| Wheel | Role | Approx size |
|---|---|---|
| `amd-torch-device-gfx1201-*` | HIP kernels (kpack) | ~48 MB |
| `torch-2.10.0+rocm7.15.0a20260627-*` | Python module + c10.dll + torch_cpu.dll | ~50-80 MB |
| `rocm-sdk-device-gfx1201-7.15.0a20260627-*` | rocm_sdk Python + runtime DLLs | ~100 MB |

**Why this matters for the fork**: the kpack alone is useless. Installing it requires the matching `torch` wheel (with `_rocm_init.py` and `lib/*.dll`) **and** the `rocm_sdk` Python package. The kpack only contributes precompiled HIP kernels that those wheels dispatch to.

The fork's Phase 6 shim bypasses `import rocm_sdk`. **With the new model**, AMD ships `rocm_sdk` as a separate wheel, so the shim is unnecessary — but the install pipeline still needs to fetch three wheels in lockstep with matched version strings.

### URLs the kpack exposed

The user found the kpack via a direct download. Probing the same domain for the matching torch + rocm-sdk wheels:

```
https://rocm.nightlies.amd.com/whl-multi-arch/torch/torch-2.10.0%2Brocm7.15.0a20260627-cp312-cp312-win_amd64.whl
    -> 404 NoSuchKey

https://repo.amd.com/rocm/whl-multi-arch/rocm-sdk-device-gfx1201/rocm_sdk_device_gfx1201-7.15.0a20260627-cp312-cp312-win_amd64.whl
    -> 403 AccessDenied (the index lists this dir but the dir listing is empty)

https://repo.amd.com/rocm/whl-multi-arch/rocm-sdk-core/rocm_sdk_core-7.15.0a20260627-cp312-cp312-win_amd64.whl
    -> 403 AccessDenied

https://repo.amd.com/rocm/whl-multi-arch/torchaudio/torchaudio-2.10.0%2Brocm7.15.0a20260627-cp312-cp312-win_amd64.whl
    -> 404 (only rocm7.13.0 torchaudio exists at this index, not 7.15)
```

The kpack was published; the matching `torch`, `rocm-sdk-core`, `rocm-sdk-device-gfx1201`, and `torchaudio-7.15` wheels were either never published, were unpublished, or were synced to a different path. This is consistent with the ROCm 10.0 release being a **partial Windows release** where not all 3 wheels of the split arrived in public mirrors.

### What we know now

1. **AMD's TheRock pipeline now ships per-GPU-arch wheel packages** as the public API. Single `torch-*-win_amd64.whl` with everything bundled is going away.
2. **The split happens between three S3 paths**. Each can be 200 / 404 / 403 independently.
3. **The split is fragile on Windows**: AMD only ships one of the three wheels to public mirrors for some build strings. Without the `rocm_sdk_core` wheel, even the kpack + torch wheel pair will not load — `import rocm_sdk` fails just like before.
4. **The fork's Phase 6 shim** is still the right workaround for the `import rocm_sdk` failure, even on this newer model. It does not depend on the wheel structure.

### What this changes for the fork

Nothing immediate. The current catalog wheels (March 2026 build, single-wheel format) still work on the user's machine because they are cached. The kpack discovery is interesting because it explains **why** AMD has not published a complete `rocm_sdk` Python wheel for Windows — they are restructuring the entire delivery model around TheRock.

For the fork to land end-to-end Windows song generation, the question is now:

> When does AMD publish **all three wheels** of a single build string on Windows?

Until then, the user's cached March 2026 build remains the only working AMD ROCm Windows PyTorch stack we have access to, and the fork's Phase 6 shim remains the correct workaround.

## The "phantom index" (Sep 23 11:32 UTC)

Probing the user's URL pattern one more time after the kpack discovery revealed:

```
https://rocm.nightlies.amd.com/whl-multi-arch/rocm-sdk-core/rocm_sdk_core-10.1.0a20260810-py3-none-win_amd64.whl
  index: lists the file
  HEAD : 404 NoSuchKey

https://rocm.nightlies.amd.com/whl-multi-arch/rocm-sdk-core/rocm_sdk_core-10.1.0a20260810-py3-none-linux_x86_64.whl
  index: lists the file
  HEAD : 404 NoSuchKey

https://rocm.nightlies.amd.com/whl-multi-arch/rocm-sdk-core/rocm_sdk_core-10.0.0a20260729-py3-none-win_amd64.whl
  index: lists the file
  HEAD : 404 NoSuchKey

https://repo.amd.com/rocm/whl-multi-arch/rocm-sdk-core/rocm_sdk_core-10.1.0a20260810-py3-none-win_amd64.whl
  HEAD : 403 AccessDenied (separate problem; whole mirror blocked)
```

**Even Linux wheels 404**. The index lists every wheel in every category (torch, torchaudio, rocm-sdk-core, rocm-sdk-device-*, rocm-sdk-libraries, rocm, rocm-bootstrap, ...). All return 404 on HEAD.

The kpack the user has (`amd_torch_device_gfx1201-2.10.0+rocm7.15.0a20260627-cp312-cp312-win_amd64.whl`) is therefore a **survivor** from a brief window when AMD's S3 sync was working. Today (Sep 23) that URL also returns 404 from CDN. The file exists only because the user downloaded it earlier.

**This is an AMD infrastructure problem, not a fork problem.** The fork's catalog URLs and discovery logic are correct; AMD's CDN just isn't serving the objects that their index claims exist.

### What would unblock the fork

1. AMD restores the S3 sync — the index is already ahead of reality
2. The user's local kpack is correct; it just needs the matching torch + rocm_sdk_core wheels to land in S3
3. After that, our Phase 6 shim can be tested against a real `import rocm_sdk` success

### What we know about the AMD TheRock release model

Phoronix coverage (Sep 2026) said *"Windows will follow the same release cadence as Linux for ROCm releases. Right now the ROCm Core SDK for Windows is a simple static package while later in the year they are working toward native Windows installer support."* The multi-arch index at `whl-multi-arch/amd-torch-device-gfx*/` is the public mirror of that future shape. Until the SDK lands, the fork cannot progress.