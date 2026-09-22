# Validation checklist — RX 9070 XT (and other RDNA4 cards)

> The fork's source patches pass the GPU-independent test suite
> (`tests/test_score.py`, `tests/test_music.py`,
> `tests/test_app.py::test_catalogue_covers_every_string`,
> `tests/test_app.py::test_gpu_profiles_and_verdict` — verified
> 66/66 on Linux/CPython 3.14). The PySide6 GUI tests and the
> `tests/test_setup.py` end-to-end installer test require Windows,
> and the AMD behaviour in particular requires a real Radeon GPU.
>
> This checklist is what to run on the day you have one. Tick as you
> go; raise an issue with the output of any failed step.

---

## A. Environment

- [ ] Windows 11 (build 26100+ recommended)
- [ ] AMD Adrenalin driver installed (any 26.x release that brings HIP 7.x)
- [ ] `rocminfo` works: `rocminfo | grep "Marketing Name"` prints
      "Radeon RX 9070 XT" (or your card)
- [ ] `nvidia-smi` is **absent** (otherwise the Setup GUI may
      misdetect — both are detected, NVIDIA wins by current logic)
- [ ] ~30 GB free on the install drive (11.5 GB AMD wheels + 7 GB
      YuE2-3B + 530 MB YuE2-Vae + 230 MB SheetSage2 + 1 GB MERT +
      overhead)
- [ ] Network reaches `rocm.nightlies.amd.com` and `huggingface.co`
      (or your mirror; the catalog has no mirror fallback yet)

## B. Setup (first run)

1. Unzip the release somewhere short, e.g. `D:\Gokuk`. Move it later
   if you must; the runtime is portable.
2. Run `GokukSetup.exe`. Watch the Graphics card card at the top:
   it should read **`RX 9070 XT · 16 GB · works in low-memory mode`**
   in yellow (`warn`). If it reads "No CUDA or ROCm graphics card
   found...", see `Diagnostics` at the bottom of this file.
3. Click Install. The download bar should advance by model first
   (YuE2-3B is the slow part), then a small archive (`therock-runtime`
   in this commit is a 500 MB placeholder — see notes below), then
   the AMD wheels (~300 MB across both runtimes).
4. After the wheels install, Setup runs a self-test on each
   Python. Look in `runtime/yue2/Logs/...` and
   `runtime/sheetsage/Logs/...`. Each should print a line like:
   `yue2 2.10.0+rocm7.12.0a20260311 True True`
   The two `True`s are `torch.version.cuda is None` and
   `torch.cuda.is_available()`. If the first is `False`, Setup raised
   *"AMD ROCm install failed: this Python is built against CUDA..."*
   — see Diagnostics.

### Notes on `archive:therock-runtime`

This entry is a 500 MB placeholder in the catalog. The actual
TheRock v4 runtime ships the HIP DLLs (`amdhip64.dll`, `librocdxg.dll`,
...) that AMD's PyTorch wheel dynamically loads at runtime. Until
this entry is replaced with a real download, you must **install
AMD's HIP runtime separately** (the Adrenalin driver includes the
runtime on Windows; verify with `where amdhip64.dll`). Without it,
the workers will fail to start with `OSError: [WinError 126]`.

This is the single biggest follow-up work item for the port — see
§ 6 of `docs/ROCM_PORT.md`.

## C. Launch

1. Run `Gokuk.exe`. The window should open within ~3 seconds. If it
   does not, check the log folder (Settings → Open log folder).
2. Open Settings. Verify:
   - **Graphics card** shows the AMD verdict as in B.2.
   - **Speed mode** dropdown has only one entry, "Safe (slower,
     most compatible)", with the hint "AMD ROCm builds run only
     in safe mode right now." underneath.
   - **Audio decoder** is unchanged from the NVIDIA flow.

## D. Generate a song (the real test)

1. On the Create tab, leave the example sample lyrics style and lyrics
   in place (English, four verses). Press **Create song**.
2. The progress card steps through Planning → Singing → Synthesizing
   → Decoding. On a 16 GB RX 9070 XT expect ~5-7 minutes for a
   3-minute song.
3. Open `runtime/yue2/Logs/...log` and confirm the two startup
   lines:
   ```
   attention backend: sdpa
   memory mode: low {... 'vae_core_frames': 512, ...}, card 16.0 GiB
   ```
   - If `attention backend: cudnn` appears, you are running an
     NVIDIA build — reinstall with `GOKUK_SETUP_VENDOR=amd`.
   - If `vae_core_frames` is 1024 on a 16 GB card, the adaptive
     sizing in `workers/yue2_worker.py::_adapt_vaae_tiles()` is not
     engaged. Inspect `torch.version.hip`.
4. When the Library card appears, click the play icon. Listen for at
   least 30 seconds. The audio should be musically coherent (singer +
   instruments). A hiss / roar / NaN-buzz means the attention or VAE
   patch is not actually being applied — file a bug with the log
   attached.
5. Open `songs/<song>/score.abc` in any text editor. It should be
   ABC notation, roughly the same length as the lyrics.

## E. Generate a cover (the harder test)

1. Switch to the Cover tab. Drag any audio file (MP3 / WAV / FLAC)
   onto the drop zone. Use a 30-60 second clip with a clear vocal
   melody for the best chance of a readable score.
2. Press **Write down the melody**. This spins up the sheetsage
   worker. Expected: progress card steps through Loading → transcribe,
   finishes in ~30-90 seconds with a score editor opening.
3. Inspect the resulting `score.abc`. If it is empty or contains
   only one bar, SheetSage2's transcription fell off the rails. The
   most common cause on AMD is the MIOpen JIT issue described in
   `Pitfalls-and-Known-Issues` § 3 — the `descript-audiotools` patch
   from `Newaiguy/YuE2-T8-ROCm` is the workaround to try.
4. Fill in lyrics + style, press **Make cover**. Same expectations
   as D, with one extra variable (the seed melody may not match your
   lyrics).

## F. Correctness signal

The most sensitive correctness check for any port is reproducibility:

1. Pick a seed (say `20260917`).
2. Use the same lyrics + style as a known NVIDIA run. The
   `multimodal-art-projection/YuE2` README links to a set of example
   lyrics; pick one short.
3. Generate. The audio length of the resulting `.flac` should match
   the NVIDIA run to **exactly** one sample (the frame boundary
   depends on the decoder, and the same kernel runs either backend,
   but if you see drift of more than a sample, the port is changing
   behaviour somewhere — likely the VAE tile size).
4. **Optional**: hexdiff a short prefix of the FLAC against the
   NVIDIA reference. They should match.

## G. Stress

1. Queue four takes back-to-back on the same lyrics with different
   seeds. Each should free its VRAM cleanly before the next starts;
   `peak_vram_gib` reported in the protocol events should not creep
   upward across takes (a leak would balloon the fourth take past
   the 16 GB card).
2. Cancel a take mid-generation. The next start should work
   without leaving a zombie worker.

## H. Failure modes (diagnostic recipes)

| Symptom                                                | First thing to check                                                                          |
|--------------------------------------------------------|------------------------------------------------------------------------------------------------|
| "No CUDA or ROCm graphics card found" verdict         | `where rocminfo` — Adrenalin installs it under `C:\Windows\System32`; if missing, reinstall driver |
| Same verdict, but `rocminfo` is on PATH                | `rocminfo | grep "Marketing Name"` — if empty, the kernel-mode driver is not loaded; reboot with amdgpu enabled in UEFI |
| `verify()` fails: "AMD ROCm install failed..."         | Re-run Setup with the `rocminfo` visible; check that the AMD nightly URL was reachable        |
| Worker crash: `OSError: [WinError 126] amdhip64.dll`   | The `archive:therock-runtime` placeholder is not a real download. Install AMD HIP runtime separately (Adrenalin ships it; copy `amdhip64.dll` to `runtime/`) |
| Audio is hiss / roar                                   | Attention backend is wrong. See D.3. Also check that the `FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` env var was set in `app/jobs/worker_proc.py` — yes, it is, in this fork |
| First song is OOM on a 16 GB card                      | `memory mode` is not `low`. Force it from the Settings card. If it is already `low`, file a bug |
| `pip install` step hangs forever                      | Network blocked `rocm.nightlies.amd.com` mid-download. Cancel and retry; if persistent, mirror the wheels locally and point the catalog at the mirror URL |

## I. Tick when you finish

When the song + cover generation completes and the audio matches a
known reference, write a one-paragraph summary into a file like
`docs/VALIDATION_RX_9070_XT.md` with:

* Windows build number
* Driver version (Settings → About or `rocminfo` header)
* `torch.__version__` and `torch.version.hip`
* Wall time for a 60 s song and a 24 s cover
* The seed and lyrics you used
* A sentence on whether the audio matches the NVIDIA reference

That document is the deliverable that closes Phase 5 of the port.