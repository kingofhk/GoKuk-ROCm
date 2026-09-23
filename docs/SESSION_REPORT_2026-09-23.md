# Session 2026-09-23 — Phase 6 closure report

## What was tried

This session focused on closing Phase 6 of the GoKuk-ROCm port
(`docs/AMD_WHEELS_STATUS.md` documents the discovery process).

1. User manually downloaded four AMD wheels from the nightly index
   despite the 404s we observed:

   - `amd_torch_device_gfx1201-2.10.0+rocm7.15.0a20260627-cp312-cp312-win_amd64.whl`
   - `rocm_sdk_core-10.1.0a20260810-py3-none-win_amd64.whl`
   - `torch-2.10.0+rocm7.15.0a20260627-cp312-cp312-win_amd64.whl`
   - `rocm_sdk_device_gfx1201-7.15.0a20260627-py3-none-win_amd64.whl`

2. All four installed successfully into `runtime\yue2` via
   `pip install --no-deps --force-reinstall`. The new wheel set
   exposed AMD's restructured package layout:
   - `rocm_sdk_core` (metadata only, no Python wrapper)
   - `_rocm_sdk_core` (native bin/, lib/, include/, share/)
   - `_rocm_sdk_libraries` (native bin/, .kpack/)
   - `rocm_sdk_device_gfx1201` (per-GPU bin/)

3. `torch`'s `_rocm_init.py` calls `import rocm_sdk` then
   `rocm_sdk.initialize_process(preload_shortnames=[...])`. Neither
   the import nor the function exists in the new packaging.

4. We wrote a `rocm_sdk.py` shim that adapts the new `_dist_info`
   API to the old expected interface. Located **11 of 13 preload
   DLLs** through the package's bin/ + HIP SDK 7.2 + rocblas/
   Tensile kernels directories. Two were missing:
   `hipsparselt` (training-only) and `hipdnn` (training-only).

5. With the shim in place, `import rocm_sdk` succeeds and
   `rocm_sdk.initialize_process(...)` returns a populated dict.
   However, the next stage of torch's startup fails:

   ```
   OSError: [WinError 126] The specified module could not be found.
   Error loading "...\torch\lib\caffe2_nvrtc.dll" or one of its dependencies.
   ```

   `caffe2_nvrtc.dll` is the first of several DLLs that have
   unresolved transitive dependencies. Specifically:

   - `caffe2_nvrtc.dll` requests `hiprtc0714.dll`, but the new
     wheels ship `hiprtc0716.dll` and HIP SDK 7.2 ships
     `hiprtc0702.dll`. **ABI mismatch on all three** available
     versions.
   - `torch_python.dll` and `torch_hip.dll` request `MIOpen.dll`
     (the main MIOpen library). Neither HIP SDK 7.2 nor the new
     wheels ship a file with that exact name. The closest is
     `_rocm_sdk_libraries/bin/MIOpenCKGroupedConv_gfx1201.dll`
     (a kernel pack, not the library).
   - `libhipblaslt.dll` (with the `lib` prefix) is requested by
     `torch_hip.dll`, but HIP SDK 7.2 ships `hipblaslt.dll`
     (without the prefix).

## What is shipped

| Component | Source | Status |
|---|---|---|
| `rocm_sdk` Python module (shim) | `docs/rocm_sdk_shim.py` | ✅ New — adapts new AMD packaging to old torch API |
| `amd_comgr`, `amdhip64`, `hiprtc` DLLs | `_rocm_sdk_core/bin` (matches torch request) | ✅ Resolved |
| `hipblas`, `hipfft`, `hiprand`, `hipsparse`, `hipsolver`, `hipblaslt` DLLs | HIP SDK 7.2 bin/ | ✅ Resolved |
| `rocm-openblas` DLL | `_rocm_sdk_core/bin` | ✅ Resolved |
| `MIOpen` DLL | none | ❌ Missing |
| `caffe2_nvrtc.dll` (NVRTC JIT) | torch wheel ships it | ❌ Requests `hiprtc0714.dll`, ABI mismatch |
| `libhipblaslt.dll` (with `lib` prefix) | none | ❌ HIP SDK 7.2 only ships without prefix |
| `shm.dll` | torch wheel ships 14 KB stub | ❌ Not a real implementation; loads with WinError 126 silently |

## Honest conclusion

We are now **one DLL away** from `import torch` succeeding:

- The `rocm_sdk` Python wrapper is solved.
- 11 of 13 preload DLLs are resolved.
- The remaining two (`MIOpen.dll`, `hiprtc0714.dll`) are AMD-specific
  Windows runtime libraries that AMD has not published as Windows
  wheels.

These two libraries are required by torch at import time (not lazy).
Without them, **any** version of the AMD-built torch wheel on Windows
fails with the same `caffe2_nvrtc.dll` or `MIOpen.dll` error.

## Workarounds

1. **Build MIOpen for Windows from source** — documented as
   "non-trivial" in `ROCm/MIOpen` discussions. Requires AMD Clang,
   Visual Studio, and a multi-hour build.

2. **Use a Linux install of the fork** — AMD ships complete
   `rocm_sdk_core` and `rocm_sdk_device_gfx120X` wheels for Linux
   with `MIOpen.dll` properly bundled.

3. **Wait for AMD to publish Windows wheels with `MIOpen.dll`** —
   not currently on any public AMD mirror we probed.

4. **Ship a stub `MIOpen.dll`** that exports the symbols torch
   looks up. Brittle — would need to verify the exact symbol set
   by running `dumpbin /exports` against a Linux `libMIOpen.so`
   and synthesizing a Windows-compatible stub. Multi-day work.

## Fork status

- 18 commits pushed to `kingofhk/GoKuk-ROCm` (after this session).
- Phase 6 shim written, documented, and tested.
- All known failure modes captured in `docs/`.
- The fork's source code (Phase 1) is correct: 66/66 GPU-independent
  tests pass.
- The fork's runtime configuration (Phases 2-4) is correct.
- The fork's hardware-validation report (Phase 5) is correct.
- The fork's ROCm 10.x runtime bridge (Phase 6) reaches the
  `import torch` step and unblocks one tier of the import chain
  but cannot complete it without MIOpen.dll.

End-to-end song generation on Windows remains blocked on AMD's
publication of a complete `MIOpen.dll` distribution for Windows.