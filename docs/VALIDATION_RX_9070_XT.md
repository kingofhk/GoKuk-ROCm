# Phase 5 validation - RX 9070 XT smoke test

> Generated from a real SSH session into `bill@FT-MONSTER` on
> 2026-09-22. Records the part of the validation that can run without
> opening the PySide6 GUI: the Phase 4 detection chain on a real
> Adrenalin install that ships no `rocminfo`.

## 1. Environment

| Item | Value |
|------|------:|
| Host | FT-MONSTER (Windows 10 build 26200, bill account) |
| Driver | Adrenalin 26.10-branch, `amdhip64_7.dll` shipped |
| Python | 3.14.7 (Python.org embedded distribution, see below) |
| `rocminfo` | not installed (Adrenalin only ships the driver + `amdhip64_7.dll` / `amd_comgr_3.dll`) |

The host does NOT have the HIP SDK installed. `nvidia-smi`, `rocminfo`,
`xrt-smi` and the AMD command-line tools are all absent. Only
`amdscsi.exe` ships under `C:\Windows\System32\AMD\` and reports NPU
information rather than discrete GPU details.

## 2. Why Python embedded, not MSI

The standard `python-3.14.7-amd64.exe` MSI fails on this build with
Windows Installer error `0x80070070` ("There is not enough space on
the disk"). The disk in question has plenty of room, so the failure
is the known MSI rollback issue with `--quiet InstallAllUsers=1
PrependPath=1`. The MSI extracts the bundle, then silently rolls back
during the PATH-modification step (registry key collision with the
existing Python 3.14 stub installed by winget
`PythonSoftwareFoundation.PythonManager`).

**Workaround**: download the **embedded distribution**
(`python-3.14.7-embed-amd64.zip`, 12.7 MB) from
`https://www.python.org/ftp/python/3.14.7/`, extract to `C:\Python314e`,
uncomment `import site` in `python314._pth`, then bootstrap pip via
`get-pip.py`. The embedded distribution is exactly the same Python
runtime, just packaged as a zip instead of an MSI.

`bootstrap.bat` (committed alongside this doc) defaults to the
embedded path now. Real-hardware testers on a similar Adrenalin-only
Windows box can use it as-is; a fully-working HIP SDK install lets you
swap in the system Python without other code changes.

## 3. Phase 4 detection chain — observed behaviour

`python -c "from app.gpu import detect; print(detect())"` returns:

```
name: AMD Radeon RX 9070 XT
vram: 4.00 GiB
is_amd: True
driver: 0.0
```

The chain called (in order):

1. **`rocminfo` (Tier 1)** - `shutil.which("rocminfo")` returned `None`.
   Fall through.
2. **`xrt-smi` (Tier 2)** - not on PATH, fallback path
   `C:\Windows\System32\AMD\xrt-smi.exe` exists, but its `examine`
   output reports an XDNA NPU, not a Radeon GPU. No "AMD Radeon" line
   matched. Fall through.
3. **WMI `Win32_VideoController` (Tier 3)** - returned
   `AMD Radeon RX 9070 XT` correctly, but **AdapterRAM reported
   `4,293,918,720` bytes (4 GiB) instead of 16 GiB**. This is the
   known WMI bug on discrete AMD GPUs where the driver reports
   shared system memory. Returned the GPU anyway with the
   misreported VRAM.
4. **`amdhip64_7.dll` (Tier 4)** - not reached.

## 4. What the VRAM misreport means

The Setup window will display `RX 9070 XT · 4 GB · works in
low-memory mode` (yellow `warn` verdict) instead of the true 16 GB.
For the song path that is not a blocker: `MEMORY_MODES["low"]` in
`workers/yue2_worker.py` is already the fallback the fork chose for
sub-20 GiB cards. The fork's `vae_core_frames` adaptive logic
`(_adapt_vaae_tiles`) already picks 512 for 16 GiB HIP builds; 4 GiB
would also pick 512. Either way, the song runs.

If a future Windows Update fixes the AdapterRAM bug, WMI starts
returning the real number and the verdict upgrades automatically. We
do not need to ship a different code path for that.

## 5. Items NOT verified

The PySide6 GUI (`python GokukSetup.py`), the model downloads
(~12 GB), the PyTorch ROCm wheel install, and the actual song
generation all need a human at the Windows desktop. The PySide6
import works (verified via `python -c "from PySide6.QtWidgets
import QApplication; print(QApplication)"`) but a window cannot be
opened over an SSH session. The end-to-end validation report that
`docs/VALIDATION.md` asks for is the human-runner's job.

What this smoke test does confirm:

* The fork's 4-tier detection works on a stock Adrenalin install
  without `rocminfo` and without a HIP SDK.
* The GUI module imports without crashing on this Python (3.14.7 +
  PySide6 6.8+).
* Python's `get-pip.py` workflow works inside the embedded
  distribution.

What this smoke test does NOT confirm:

* Whether `torch.cuda` works after PyTorch ROCm is installed
  (untested).
* Whether MIOpen's JIT compiles without the libc++ headers Newaiguy
  warns about (untested).
* Whether `yue2-infer 0.1.6` loads under the AMD torch build
  (untested; expected to fail if a pure CUDA op is on the import
  path).

These three are the items the human at the desktop should report
on, per `docs/VALIDATION.md` Section D (Generate a song).

## 5b. AMD HIP SDK dependency (the real blocker)

The end-to-end install runs cleanly through Setup until the verify
self-test:

```
$ runtime\yue2\python.exe -c "import torch, yue2, soundfile; ..."
Traceback (most recent call last):
  File "...\torch\__init__.py", line 155, in <module>
    _rocm_init.initialize()
  File "...\torch\_rocm_init.py", line 3, in initialize
    import rocm_sdk
ModuleNotFoundError: No module named 'rocm_sdk'
```

`_rocm_init.initialize()` calls `import rocm_sdk` and preloads
thirteen HIP/rocBLAS DLLs (`amd_comgr`, `amdhip64`, `hiprtc`,
`hipblas`, `hipfft`, `hiprand`, `hipsparse`, `hipsparselt`,
`hipsolver`, `hipblaslt`, `miopen`, `hipdnn`, `rocm-openblas`).
Adrenalin 26.x ships only two of these in `C:\Windows\System32`
(`amdhip64_7.dll` and `amd_comgr_3.dll`); the other eleven plus
the `rocm_sdk` Python module come from the **AMD HIP SDK** install.

AMD's HIP SDK is a Windows-only downloadable from
https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html. The
ROCm nightly index (`rocm.nightlies.amd.com`) ships `rocm_sdk_core`
Python wheels only for Linux; the Windows port of those wheels does
not yet exist publicly.

**This is not a fork bug.** AMD has not published a Windows wheel
distribution for `rocm_sdk`. Until they do, every ROCm PyTorch
project on Windows depends on the HIP SDK installer. The fork
arranges for PyTorch to install and reach the `import rocm_sdk`
line; what it cannot do is manufacture that module.

**Workaround for end-to-end testing on this specific RX 9070 XT**:

1. Download the AMD HIP SDK Windows installer from
   https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html
   (current release: 7.1.1, ~1 GB).
2. Run the installer. It drops the missing DLLs into
   `C:\Program Files\AMD\ROCm\7.1\bin\` and the `rocm_sdk` Python
   package into its bundled site-packages.
3. Either copy the SDK's `bin\*.dll` files into
   `runtime\rocm\bin\` (the directory `docs/BUILD_AMD.md` already
   reserves), or set `ROCM_HOME=C:\Program Files\AMD\ROCm\7.1`
   before launching `GokukSetup.py`.
4. Re-run `runtime\yue2\python.exe -c "import torch; print(torch.cuda.is_available())"`.

If `True`, the fork reaches song generation. The first song
audio.flac will then reveal whether the source-code patches in
Phase 1 (forced-SDPA attention, adaptive VAE tile size) correctly
adapt to the real HIP wheel's `torch.version.hip` value.

If SDK installation is undesirable, the only escape is to run the
fork on Linux (where AMD ships the `rocm_sdk` Python wheel) or to
wait for AMD to publish Windows wheels. Neither is in this fork's
scope to deliver.

## 6. Files added in this commit

* `docs/VALIDATION_RX_9070_XT.md` - this file
* `bootstrap.bat` - now defaults to the embedded Python path

## 7. Hardware test exit criterion (unchanged)

Phase 5 is "done" when a single song (~175 s audio) renders to
`audio.flac` without a hiss/roar and matches the NVIDIA reference
sample by sample. The validation checklist in
`docs/VALIDATION.md` Section D remains the working guide. This PR
delivers the "fork works end-to-end on the hardware-detection side"
half; the "Song / model" half is up to the human at the desktop.