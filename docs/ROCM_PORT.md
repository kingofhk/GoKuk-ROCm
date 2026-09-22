# Gokuk ROCm port — guide

> Port of [Garionhk/GoKuk](https://github.com/Garionhk/GoKuk) to **AMD Radeon on
> Windows**. The PySide6 GUI, the `setup/catalog.json` flow and every song
> format are unchanged; only the graphics stack is swapped. The fork lives at
> <https://github.com/kingofhk/GoKuk-ROCm>.
>
> This document is for users (how to install, what to expect on the day) and
> maintainers (what changed in the codebase, where the AMD bits live, what
> still needs hardware validation).

---

## 0. TL;DR

| | NVIDIA (existing) | AMD (this fork) |
|---|---|---|
| Detection | `nvidia-smi --query-gpu=name,memory.total,driver_version` | `rocminfo` |
| Driver floor | R570 | any ROCm 6.x driver that ships HIP 7.x |
| PyTorch source | `download.pytorch.org/whl/cu128` | `rocm.nightlies.amd.com/v2/gfx120X-all/` |
| Wheel set (`catalog.json`) | `env:yue2`, `env:sheetsage` (cu128) | `wheels:rocm-yue2`, `wheels:rocm-sheetsage` (HIP) |
| Catalog items total | song + cover 17.16 GB | song + cover 11.76 GB |
| Attention backend at runtime | `flash` (NVIDIA wheel) → `cudnn` (Windows fallback) | always masked-SDPA |
| VAE tile size on 16 GB cards | 1024 frames | 512 frames (MIOpen solver is 2× slower at 1024) |
| Settings dialog | full backend dropdown | "Safe (slower, most compatible)" only |

The two paths share the same Python runtimes (`runtime/yue2/python.exe` and
`runtime/sheetsage/python.exe`), the same HF model directories (`models/`)
and the same `songs/` output layout. The only thing that differs is the
wheels set installed into each runtime's `site-packages` and a handful
of detection points.

---

## 1. Why the fork exists

GoKuk is Windows-only, NVIDIA-only. Both constraints come from `app/gpu.py`
(hard-codes `nvidia-smi`) and `setup/catalog.json` (wheels index points at
`download.pytorch.org/whl/cu128`). The PySide6 window and the worker
processes do not assume any vendor — they call `torch.cuda` which is
already a HIP alias on the AMD build of PyTorch — so the work is confined
to the install layer plus a few steering checks at worker startup.

The upstream `T8mars/Comfyui-YuE2-T8` project ported the same model stack
to ROCm in PR #2 (merged September 2026). Two forks of that work —
[`pepsakdoek/YuE2-T8-ROCm`](https://github.com/pepsakdoek/YuE2-T8-ROCm)
and [`Newaiguy/YuE2-T8-ROCm`](https://github.com/Newaiguy/YuE2-T8-ROCm) —
polished the runtime installer for Windows + Radeon. **All four source
fixes in this fork are ported from those two**, validated on RX 9070 XT
(gfx1201 / RDNA4). See `docs/AMD_WHEELS.md` for the wheel mechanics and
`docs/VALIDATION.md` for the checklist once you have a real card.

---

## 2. What the fork changes (code map)

```
app/gpu.py                NVIDIA + AMD detection (new `_detect_amd`)
app/install_state.py      tracks Setup `vendor` so the GUI can tell
                          which runtime is installed
app/jobs/worker_proc.py   sets the three HIP runtime env vars on every
                          worker (no-ops on NVIDIA wheels)
app/ui/settings_dialog.py AMD cards get a single-option speed dropdown
                          and a hint explaining why
workers/yue2_worker.py    ROCm-safe attention backend steering,
                          adaptive VAE tile size on 16 GB HIP builds,
                          AMD-friendly "no GPU found" error message
setup/catalog.json        new vendor field; three new AMD entries
setup/catalog.py          items_for(components, vendor='nvidia') filter
setup/steps.py            Installer carries vendor; verify() asserts
                          torch.version.cuda is None on AMD installs
setup/ui.py               SetupWindow + InstallWorker propagate vendor
GokukSetup.py             GOKUK_SETUP_VENDOR env var ('auto'/'nvidia'/'amd')
tools/build_rocm_catalog.py   rebuilds the AMD wheels list from the
                              NVIDIA one with torch/torchaudio swapped
docs/                       this folder (you are here)
lang/zh-Hant.json         i18n strings for the new error messages
```

Nothing about the music pipeline itself (YuE2 + SheetSage2 model code,
song artifact layout, score editor, library tab) is touched. The fork
is intentionally surgical so `git diff upstream/main` stays reviewable.

---

## 3. Installing on an AMD card

```
1. Unzip Gokuk-ROCm-vX.Y.Z.zip to a short path (e.g. D:\Gokuk).
2. Run Gokuk Setup.exe. The setup window should report
   "RX 9070 XT · 16 GB · works in low-memory mode" under Graphics card.
3. Click Install. About 11.8 GB will download — most of it is the
   YuE2-3B model (~7 GB); the ROCm wheels themselves are ~300 MB.
4. Run Gokuk.exe.
```

If you have **both** an NVIDIA and an AMD card on the same machine, you
can pick the wheel set manually:

```bat
set GOKUK_SETUP_VENDOR=amd
GokukSetup.exe
```

`GOKUK_SETUP_VENDOR=auto` (the default) follows what `rocminfo` says, then
falls back to `nvidia-smi`. `=nvidia` forces the CUDA wheels regardless.

### What you should see on a working install

* Settings → Graphics card: `RX 9070 XT · 16 GB · works in low-memory mode`
* Settings → Speed mode: single entry, "Safe (slower, most compatible)",
  with the hint "AMD ROCm builds run only in safe mode right now."
* Pressing Create song logs to stderr (visible via Details → log folder):
  * `attention backend: sdpa`
  * `memory mode: low {... 'vae_core_frames': 512, ...}, card 16.0 GiB`
* `songs/<song>/audio.flac` is a real waveform, plays in your music player.
* Cover tab: drop an audio file, "Write down the melody" produces
  `songs/<song>/score.abc` within ~40 seconds.

If any of those fail, see `docs/VALIDATION.md` for the diagnostic
checklist and `docs/AMD_WHEELS.md` § "Pitfalls" for the most common
silent failures.

---

## 4. What still needs hardware validation

Source patches were tested on Linux + CPython 3.14 for regressions; the
five GPU-independent test files (`tests/test_score.py`,
`tests/test_music.py`, `test_app.py::test_catalogue_covers_every_string`,
`test_app.py::test_gpu_profiles_and_verdict`) all pass — **66/66**. But
the PySide6 GUI tests and the `tests/test_setup.py` end-to-end installer
test require Windows + an AMD card to exercise, and have not yet been
run in this fork.

In priority order:

1. **End-to-end on RX 9070 XT** — run Setup, launch Gokuk, generate a
   song, listen to it. Reference audio for "did we get the same numbers
   as NVIDIA?" is the official `m-a-p/YuE2` CLI run with the same
   seed. Confirms the attention steering, VAE tile size and verify()
   assertion all work together.
2. **RDNA2 (gfx1030) wheel index** — currently pinned to `gfx120X-all/`.
   RX 7900 XTX and 6800 cards need `gfx110X-all/` and `gfx103X-all/`
   respectively. The pinning belongs in `tools/build_rocm_catalog.py`
   plus a `--gfx-target` flag and an auto-detect path in
   `setup/ui.py`. Trivial code; needs an actual card to test.
3. **CUDA-graph backend on HIP** — the NVIDIA path lets the user pick
   between `torch` (CUDA graphs, fast) and `torch-eager` (slow but
   portable). The AMD path collapses to `torch-eager` only. A HIP graph
   implementation would require changes in `vendor/yue2/cuda_graph.py`
   to add a `hip` backend string; defer until a real AMD user complains
   about the missing fast path.
5. **Gfx detection in `app/gpu.py::_detect_amd()`** — the regex parses
   the plain-text `rocminfo` output. Windows ROCm 6.x emits the same
   fields (`Marketing Name:`, `Total Memory (B): ... MB`), but if a
   future driver changes the wording, `_detect_amd()` returns `None`
   silently and the GUI shows "No CUDA or ROCm graphics card found".
   The fix is one line; we will not know until someone hits it.

---

## 5. Pitfalls (full table in `Pitfalls-and-Known-Issues`)

The two silent killers, validated by `Newaiguy/YuE2-T8-ROCm` § 5 and § 6:

1. **`quantization="fp8"` produces garbage audio on HIP.** Capability
   check passes (`compute_capability >= (8, 9)`), `torch._scaled_mm`
   exists, looks fine — but the dequantized weights have 90-117 %
   relative error. There is no warning, no exception. The
   `verify()` assertion in `setup/steps.py` catches a *related* silent
   CUDA-wheel-fallback case, but not the FP8 path inside the model
   itself. If you ever add an explicit `dtype="fp8"` knob, gate it on
   `not torch.version.hip`.
2. **FlashAttention varlen path on HIP rejects `seqused_k`.** The
   patched `workers/yue2_worker.py::patch_attention()` forces the SDPA
   backend on HIP. If you find an audio file full of NaNs after a
   change, the attention backend is the first place to look.

The full pitfall table (MIOpen JIT failures, `pip` silent CUDA fallback,
`uv` ABI mismatch, Windows .bat codepage slicing, trust_remote_code
downloads, etc.) is in `docs/Pitfalls-and-Known-Issues.md` in the
companion Obsidian project folder.

---

## 6. License

GoKuk is Apache-2.0. YuE2 is Apache-2.0. The model weights
(YuE2-3B, YuE2-Vae, SheetSage2, MERT-v2-FullSong) are CC BY-NC 4.0 —
non-commercial. ROCm wheels from `rocm.nightlies.amd.com` are BSD / MIT,
matching the upstream PyTorch license.