# AMD wheels — selection, source, rebuild

> How the AMD wheel list in `setup/catalog.json` is built, where the
> URLs come from, how to refresh them, and the gotchas around the
> AMD nightly index.

---

## 1. The two AMD entries

The AMD runtime is the same shape as the NVIDIA one: two embedded
Python installs (yue2 = Python 3.12, sheetsage = Python 3.11) with their
own wheel sets, sharing the model directory and the song output layout.
The only thing that changes is the wheels list inside
`setup/catalog.json`:

| NVIDIA item id           | AMD item id              | Wheels | Total |
|--------------------------|--------------------------|-------:|------:|
| `env:yue2`               | `wheels:rocm-yue2`       |     34 | 311 MB |
| `env:sheetsage`          | `wheels:rocm-sheetsage`  |     36 | 372 MB |

The non-torch wheels (transformers, soundfile, huggingface_hub, …) are
copied wholesale from the NVIDIA list — same version, same URL, same
sha256. They are platform wheels (`cp312-cp312-win_amd64` /
`py3-none-any`), not torch ABI, so they load fine in either runtime.

The two wheels that change are `torch` and `torchaudio`. Their URLs
point at AMD's TheRock nightly index, the package source pinned to a single
build tuple so ABI lines up.

---

## 2. AMD nightly index — current state

The wheels in this fork come from
`https://rocm.nightlies.amd.com/v2/gfx120X-all/`. As of this commit:

```
torch     2.10.0+rocm7.12.0a20260311  (latest nightly; 2026-03-11)
torchaudio 2.10.0+rocm7.12.0a20260311
```

The index hosts a `cp312` wheel for Python 3.12 and a `cp311` wheel for
Python 3.11, which is exactly what GoKuk's two runtimes need.

**Important: the nightly index is not kept current.** The wheels we
pin were last uploaded on **2026-03-11**, six months before this fork
was cut. Newaiguy's reference work used the `2.11.0+rocm7.13.0a20260416`
build from a faster-moving index that AMD seems to have rolled off
public access for. If the wheels you see in the index at run time are
older than what this fork ships, raise an issue and we re-run
`tools/build_rocm_catalog.py` with the latest URLs.

---

## 3. Rebuilding the AMD wheels list

`tools/build_rocm_catalog.py` regenerates `wheels:rocm-yue2` and
`wheels:rocm-sheetsage` from the existing NVIDIA items. It copies the
NVIDIA wheel list verbatim and replaces `torch` + `torchaudio` URLs.

```bash
# from the repo root
python tools/build_rocm_catalog.py \
    --torch-url "https://rocm.nightlies.amd.com/v2/gfx120X-all/torch-2.10.0%2Brocm7.12.0a20260311-cp312-cp312-win_amd64.whl" \
    --torch-size 267616266 \
    --torchaudio-url "https://rocm.nightlies.amd.com/v2/gfx120X-all/torchaudio-2.10.0%2Brocm7.12.0a20260311-cp312-cp312-win_amd64.whl" \
    --torchaudio-size 402431 \
    --yue2-id env:yue2 --rocm-yue2-id wheels:rocm-yue2

python tools/build_rocm_catalog.py \
    --torch-url "https://rocm.nightlies.amd.com/v2/gfx120X-all/torch-2.10.0%2Brocm7.12.0a20260311-cp311-cp311-win_amd64.whl" \
    --torch-size 267584704 \
    --torchaudio-url "https://rocm.nightlies.amd.com/v2/gfx120X-all/torchaudio-2.10.0%2Brocm7.12.0a20260311-cp311-cp311-win_amd64.whl" \
    --torchaudio-size 401042 \
    --yue2-id env:sheetsage --rocm-yue2-id wheels:rocm-sheetsage
```

Both invocations read the same `setup/catalog.json`, find the existing
NVIDIA source item, copy its wheels, and overwrite the AMD placeholder
entries in place. After both calls, the file is self-consistent.

To find the latest nightly URL + size:

```bash
curl -s https://rocm.nightlies.amd.com/v2/gfx120X-all/torch/ | \
    grep -oE 'torch-2\.[0-9]+\.[0-9]+%2Brocm7\.[0-9.]+a[0-9]+-cp312-cp312-win_amd64\.whl' | \
    sort -u | tail -1
curl -sI "https://rocm.nightlies.amd.com/v2/gfx120X-all/<URL_FROM_ABOVE>" | \
    grep -i 'content-length'
```

Replace `cp312` with `cp311` for the sheetsage runtime, and
`gfx120X-all` with the right one for your card (see § 4).

---

## 4. gfx targets

| GPU                       | gfx target   | Index path                      |
|---------------------------|--------------|---------------------------------|
| RX 9070 / 9070 XT         | `gfx120X-all`| `rocm.nightlies.amd.com/v2/gfx120X-all/` |
| RX 7900 GRE / 7900 XT/XTX | `gfx110X-all`| `rocm.nightlies.amd.com/v2/gfx110X-all/` |
| RX 6800 / 6900 XT         | `gfx103X-all`| `rocm.nightlies.amd.com/v2/gfx103X-all/` |
| Older (Vega, etc.)        | unsupported   | —                               |

The fork ships `gfx120X` (RX 9070 XT) only. To target a different card:

1. Re-run `tools/build_rocm_catalog.py` with URLs pointing at the right
   index.
2. The runtime installer does not need to change — it downloads whatever
   the catalog says.
3. `workers/yue2_worker.py::is_rocm_build()` and `app/gpu.py::_detect_amd()`
   are gfx-version-agnostic.

---

## 5. SHA256 — known weak point

The wheel entry records a `sha256` field. For the torch and torchaudio
wheels in this commit, that field holds the S3 multi-part upload ETag,
which is **not** the real SHA256 of the file. The ETag
`33c935f090dd0705c3992a62ff07e7e5-32` is the hash AMD's S3 returns; the
real digest has to be computed locally after download.

The Setup installer (`setup/download.py`) only verifies the `sha256`
field when it is non-empty. If we set it to the ETag and the ETag does
not match the actual file hash, install will fail with a confusing
hash-mismatch error. So in this commit we set `sha256=""` for the two
big ROCm wheels, **skipping** integrity verification — install proceeds,
byte-count is the only check.

The fix is to download each ROCm wheel locally once, compute its true
SHA256, and re-run `tools/build_rocm_catalog.py --torch-sha256 <hex>`.
Hardware testing on a real Windows box is the moment to do this; without
the wheel on disk there is nothing to hash.

For the ~30 non-torch wheels, the SHA256 is the genuine PyPI one copied
from the NVIDIA list — those are fine.

---

## 6. Why not Pinia or rmx wheels?

We considered three sources for the ROCm PyTorch wheel:

| Source                                | Pro                          | Con                                          |
|---------------------------------------|------------------------------|----------------------------------------------|
| AMD nightly (`rocm.nightlies.amd.com`) | Windows wheels, gfx-tagged   | Stale, no SHA256                             |
| TheRock v4 release zip                | Bundled CUDA/ROCm libs       | Heavyweight — need separate install path     |
| Build PyTorch from source             | Latest everything            | Build takes hours, needs ROCm toolchain      |

We chose the nightly index because it matches the way GoKuk already
delivers NVIDIA wheels (one URL per wheel, hash + size verified, no
manual build step). The downsides are tracked above. Switching to
TheRock is a future-work item; it would mean adding a step to extract
HIP runtime DLLs and adding them to `Gokuk.spec` (see § 6 of
`docs/ROCM_PORT.md`).

---

## 7. Pitfalls (compressed; full table elsewhere)

* **pip silently falls back to a CUDA wheel if the AMD wheel download
  fails.** `setup/steps.py::verify()` catches this by asserting
  `torch.version.cuda is None` after install. The error you get if it
  trips is: *"AMD ROCm install failed: this Python is built against
  CUDA, not HIP."*
* **`uv` resolves `torch` and `torchaudio` independently and may produce
  an ABI-mismatched pair.** Both AMD entries in this fork pin the same
  `2.10.0+rocm7.12.0a20260311` build date; reinstall with
  `--reinstall` (which GoKuk's installer does) overwrites whatever
  mismatch uv would otherwise introduce.
* **PyTorch 2.9.0 needs `hipsparselt`, which AMD 7.10 SDKs do not
  ship.** This fork pins 2.10.0 specifically to dodge that issue; if
  you bump to 2.9.x, expect `Unknown rocm library 'hipsparselt'`.
* **`descript-audiotools` (a transitive dep of `demucs`) needs a
  patch on torch ≥ 2.9.** GoKuk does not ship Seed-VC / RVC, so this
  is not our wheel list. Mentioning here only because it bites anyone
  who adds voice-conversion deps later.