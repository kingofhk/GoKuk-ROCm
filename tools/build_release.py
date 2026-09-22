"""Build the portable release: dist/Gokuk/ and release/Gokuk-v<version>.zip.

    python tools/build_release.py [--vendor amd|nvidia]

1. Clears Python caches out of workers/ (they would ship as data files).
2. Runs PyInstaller on Gokuk.spec - both programs into one folder. With
   --vendor=amd, also looks at runtime/rocm/bin/*.dll for HIP/rocBLAS
   DLLs and ships them alongside the EXEs.
3. Adds README.txt and the licence notes.
4. Zips the folder. The zip is small (~60 MB): runtimes and models are not in
   it - Gokuk Setup downloads them on the user's machine.

The build Python needs PySide6, requests and pyinstaller (requirements-build.txt).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.0"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"

README = """Gokuk {version}
============

Make songs from a style and lyrics, and covers from recordings - on your own
graphics card. Powered by YuE2 and SheetSage2 (m-a-p).

FIRST TIME
  1. Put this folder somewhere with about 25 GB free, for example D:\\Gokuk
     (not inside OneDrive or Program Files).
  2. Double-click "Gokuk Setup.exe". It downloads the music engine and models
     (about 16 GB) with progress shown. You can stop and re-run it at any time;
     it carries on where it left off.
  3. Double-click "Gokuk.exe".

NEEDS
  Windows 10/11 64-bit, a graphics card with 12 GB or more (16 GB+ recommended,
  24 GB fastest). For NVIDIA: any RTX-class card from R570 driver onward.
  For AMD Radeon (RX 9070 / 9070 XT / 7900 / 6800): Adrenalin driver from
  2026 with HIP 7.x support and the AMD HIP runtime installed
  (C:\\Windows\\System32\\amdhip64_7.dll).

PORTABLE
  Everything lives in this folder: runtime\\, models\\, songs\\, settings.json.
  Nothing is written to the registry or your user profile. Copy the whole folder
  to another drive or PC and it keeps working.

LICENCES
  The YuE2, SheetSage2 and MERT model weights are licensed CC BY-NC 4.0
  (non-commercial use only); their licence files are in models\\<name>\\ after
  Setup has run. The YuE2 code is Apache-2.0. Gokuk's score reader is adapted
  from YuE2's abc_tools.py; see licences\\.
"""


def run(cmd: list[str], env: dict | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", default="nvidia", choices=("nvidia", "amd"),
                        help="Which wheel set the bundled EXEs expect (default nvidia).")
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()
    vendor = args.vendor

    for cache in (ROOT / "workers").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    env = None
    if vendor == "amd":
        env = {**__import__("os").environ, "GOKUK_BUILD_VENDOR": "amd"}
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DIST), "--workpath", str(BUILD), "Gokuk.spec"], env=env)
    out = DIST / "Gokuk"
    for cache in out.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    (out / "README.txt").write_text(README.format(version=args.version), encoding="utf-8")
    licence = ROOT / "LICENSE.txt"
    if licence.is_file():
        shutil.copyfile(licence, out / "LICENSE.txt")
    # Third-party notices (app/score/abc_dialect.py is adapted Apache-2.0 code from YuE2).
    shutil.copytree(ROOT / "licences", out / "licences", dirs_exist_ok=True)

    RELEASE.mkdir(exist_ok=True)
    archive = RELEASE / f"Gokuk-v{args.version}-{vendor}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file in sorted(out.rglob("*")):
            if file.is_file():
                z.write(file, Path("Gokuk") / file.relative_to(out))
    print(f"\nRelease: {archive}  ({archive.stat().st_size / 2**20:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
