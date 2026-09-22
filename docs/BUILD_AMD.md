# runtime/rocm/bin/

This directory is the drop zone for AMD HIP and rocBLAS runtime DLLs that
need to be bundled with the AMD build of Gokuk.

When you run `python tools/build_release.py --vendor=amd`, PyInstaller
globs `runtime/rocm/bin/*.dll` and ships whatever is here alongside the
two EXEs. The user gets a portable Gokuk that does not require a
separate AMD HIP SDK install.

## What to drop here

The minimum set, validated by the `llama.cpp win-rocm-7.14` regression
report (https://github.com/ggml-org/llama.cpp/issues/26996):

| File                          | Source                                       |
|-------------------------------|-----------------------------------------------|
| `amdhip64_7.dll`              | Adrenalin driver (C:\Windows\System32)         |
| `amd_comgr_3.dll`             | Adrenalin driver (C:\Windows\System32)         |
| `hipblas.dll`                 | AMD ROCm SDK or HIP SDK                       |
| `hipblaslt.dll`               | AMD ROCm SDK or HIP SDK                       |
| `rocblas.dll`                 | AMD ROCm SDK or HIP SDK                       |
| `rocsolver.dll`               | AMD ROCm SDK or HIP SDK                       |
| `rocsparse.dll`               | AMD ROCm SDK or HIP SDK                       |
| `rocm_kpack.dll`              | AMD ROCm SDK or HIP SDK                       |
| `hipfft.dll`                  | AMD ROCm SDK or HIP SDK                       |

Directories you also need (PyInstaller bundles DLLs but not whole
directories; copy these by hand or update `Gokuk.spec`):

| Directory                | Purpose                                       |
|--------------------------|-----------------------------------------------|
| `hipblaslt/`             | Tensile kernel libraries for hipBLASLt       |
| `rocblas/`               | Tensile kernel libraries for rocBLAS         |

The full set is approximately **500 MB** unpacked. The
`archive:therock-runtime` entry in `setup/catalog.json` is a
placeholder for the upstream TheRock Windows tarball that ships all of
this in one download; once a stable URL is published for it, this
README will be replaced by the install path.

## Where to find the DLLs on a Windows machine with Adrenalin installed

```powershell
# After installing the AMD HIP SDK:
$env:ProgramFiles\AMD\ROCm\7.14\bin\*.dll   # HIP runtime
$env:ProgramFiles\AMD\ROCm\7.14\bin\hipblaslt\
$env:ProgramFiles\AMD\ROCm\7.14\bin\rocblas\
```

If the HIP SDK is not installed (only the driver), at minimum copy
`C:\Windows\System32\amdhip64_7.dll` and `C:\Windows\System32\amd_comgr_3.dll`
to this directory and the rest from a download of the AMD HIP SDK
installer.

## Why not just rely on system32?

`amdhip64_7.dll` is shipped by the Adrenalin driver to `C:\Windows\System32`
and PyInstaller's launcher does add that directory to the DLL search
path at process start. The hipBLAS / rocBLAS libraries are **not**
shipped by the driver — they only come from the HIP SDK or a ROCm SDK
install. That is why we bundle them.

Once AMD ships a self-contained Windows ROCm runtime (the
ROCm Windows Tarball linked from the install docs) we will switch the
catalog to download it as a single archive and drop this README.