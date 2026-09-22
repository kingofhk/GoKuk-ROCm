# -*- mode: python ; coding: utf-8 -*-
"""Gokuk and Gokuk Setup, built into one portable folder.

    python tools/build_release.py --vendor=amd        (or: pyinstaller --noconfirm Gokuk.spec)

Two programs share one _internal folder, so PySide6 is shipped once. Neither
contains torch: the engines are downloaded by Setup into runtime/.

Shipped as plain files beside the code, because they are read (or run) from
disk rather than imported: the language catalogue, the icons, the download
catalogue and its lock files, and the worker scripts that the downloaded
Pythons execute.

AMD-specific bits:

* GOKUK_BUILD_VENDOR=amd   tells PyInstaller to also copy a small set of
  AMD runtime DLLs alongside the two EXEs. The Python interpreters inside
  runtime/yue2/ and runtime/sheetsage/ are downloaded by Setup on the
  user's machine and link against the AMD HIP runtime at runtime; this
  keeps the bundled EXEs usable as a launcher even before Setup runs.

  Concretely, GOKUK_BUILD_VENDOR=amd tells PyInstaller to look for:

      <repo>/runtime/rocm/bin/*.dll

  and add them under the same _internal directory as the rest of the
  bundled binaries. The directory is created by ``setup/steps.py`` when
  Setup runs the AMD install path; for a build-time dry-run you can
  populate it with the same DLLs that Adrenalin drops into
  ``C:\\Windows\\System32`` (notably ``amdhip64_7.dll``) and any
  extra HIP/rocBLAS DLLs you want bundled.

* Without GOKUK_BUILD_VENDOR (or =nvidia), this spec builds the original
  GoKuk release unchanged.
"""
import os
import sys

sys.path.insert(0, SPECPATH)
from build_common import EXCLUDES, strip_unused

VENDOR = os.environ.get("GOKUK_BUILD_VENDOR", "nvidia").strip().lower()
if VENDOR not in ("nvidia", "amd"):
    VENDOR = "nvidia"

DATAS = [
    ("lang", "lang"),
    ("assets/icons", "assets/icons"),
    ("setup/catalog.json", "setup"),
    ("setup/locks", "setup/locks"),
    ("workers", "workers"),
]

#: AMD DLLs to bundle next to the EXE. The directory layout matches what
#: ``setup/steps.py`` drops into ``runtime/rocm/bin/`` on the user's
#: machine, and what ``docs/BUILD_AMD.md`` tells the maintainer to
#: populate before running ``tools/build_release.py --vendor=amd``.
#: PyInstaller resolves the glob at build time, so the same glob picks
#: up whatever the build host happens to have.
_AMD_DLL_GLOB = os.path.join("runtime", "rocm", "bin", "*.dll")


def _amd_binaries():
    if VENDOR != "amd":
        return []
    import os.path

    # PyInstaller sets SPECPATH to the directory that contains the spec
    # file. We use it directly as the glob root - no os.path.dirname.
    found = []
    import glob as _glob

    for src in _glob.glob(os.path.join(SPECPATH, _AMD_DLL_GLOB)):
        name = os.path.basename(src)
        # PyInstaller's binaries list is [(name, path, 'BINARY')]. We mirror
        # the existing analysis() shape so the COLLECT step picks them up.
        found.append((name, src, "BINARY"))
    print(f"[Gokuk.spec] VENDOR={VENDOR}, found {len(found)} AMD DLLs under "
          f"{os.path.join(SPECPATH, _AMD_DLL_GLOB)}")
    return found


def analysis(script, extra_excludes=()):
    a = Analysis(
        [script],
        pathex=[SPECPATH],
        binaries=_amd_binaries(),
        datas=DATAS,
        hiddenimports=[],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=EXCLUDES + list(extra_excludes),
        noarchive=False,
        optimize=0,
    )
    a.binaries = strip_unused(a.binaries)
    return a


def program(a, name, icon):
    return EXE(
        PYZ(a.pure),
        a.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        icon=[icon],
    )


app = analysis("Gokuk.py")
setup = analysis("GokukSetup.py", extra_excludes=["PySide6.QtMultimedia"])

app_exe = program(app, "Gokuk", "assets/icons/Gokuk.ico")
setup_exe = program(setup, "Gokuk Setup", "assets/icons/GokukSetup.ico")

coll = COLLECT(
    app_exe, app.binaries, app.datas,
    setup_exe, setup.binaries, setup.datas,
    strip=False,
    upx=False,
    name="Gokuk",
)
