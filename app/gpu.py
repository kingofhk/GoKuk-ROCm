"""What graphics card this machine has, asked of the driver CLI.

Neither Gokuk nor Gokuk Setup imports torch, so the card is identified the way
the driver itself reports it. nvidia-smi ships with every NVIDIA driver;
rocminfo ships with every ROCm install.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from app.i18n import t

#: torch 2.10 cu128 needs driver R570+, torch 2.8 cu126 needs R560+.
MIN_DRIVER = 570.0


@dataclass
class GPU:
    name: str
    vram_mib: int
    driver: str
    #: True when this GPU was reported by ``rocminfo`` rather than ``nvidia-smi``.
    #: AMD cards carry a placeholder driver string and skip the NVIDIA driver
    #: version check.
    is_amd: bool = False

    @property
    def vram_gib(self) -> float:
        return self.vram_mib / 1024

    @property
    def driver_number(self) -> float:
        try:
            major, _, minor = self.driver.partition(".")
            return float(f"{int(major)}.{int(minor or 0):02d}")
        except ValueError:
            return 0.0


def _detect_nvidia() -> GPU | None:
    """The largest NVIDIA card, or None if there is none (or no driver)."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    cards = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3 and parts[1].isdigit():
            cards.append(GPU(parts[0], int(parts[1]), parts[2]))
    return max(cards, key=lambda g: g.vram_mib) if cards else None


def _parse_rocm_plain(out: str) -> GPU | None:
    """Parse ``rocminfo`` plain-text output (Windows and Linux)."""
    name = None
    vram_mib = 0
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("Marketing Name:"):
            name = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Name:"):
            if not name:
                candidate = stripped.split(":", 1)[1].strip()
                if candidate and candidate.lower() != "gfx":
                    name = candidate
        elif "Total Memory" in stripped and "MB" in stripped:
            match = re.search(r"([\d.]+)\s*MB", stripped)
            if match:
                vram_mib = max(vram_mib, int(float(match.group(1))))
    if not name or vram_mib <= 0:
        return None
    return GPU(name=name, vram_mib=vram_mib, driver="0.0", is_amd=True)


def _amd_total_memory_from_xrt(out: str) -> int:
    """Best-effort MB extraction from ``xrt-smi examine`` output."""
    for line in out.splitlines():
        if "Total Memory" in line and "MB" in line:
            match = re.search(r"([\d.]+)\s*MB", line)
            if match:
                return int(float(match.group(1)))
    return 0


def _detect_amd() -> GPU | None:
    """The largest AMD card readable by ``rocminfo``, or None on failure.

    Detection chain (first non-empty wins):

    1. ``rocminfo`` plain text (Linux ROCm and Windows HIP SDK installs).
    2. ``xrt-smi`` (XRT/XDNA SMI ships with Adrenalin driver only).
    3. WMI ``Win32_VideoController`` (always available; reports AMD by
       ``VideoProcessor`` substring; reports wrong AdapterRAM, but that's
       good enough for the verdict).
    4. AMD driver DLL presence as a last-resort hint (``amdhip64_7.dll``
       ships with Adrenalin 26.x even without the HIP SDK).

    Returns a ``GPU`` with a placeholder driver string (ROCm is reported
    by the runtime, not the card).
    """
    # Tier 1: rocminfo (unchanged from before).
    exe = shutil.which("rocminfo")
    if exe:
        try:
            out = subprocess.run(
                [exe], capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        card = _parse_rocm_plain(out)
        if card:
            return card

    # Tier 2: xrt-smi (ships with Adrenalin; reports NPU/GPU at once).
    exe = shutil.which("xrt-smi")
    if not exe:
        # xrt-smi is sometimes under C:\Windows\System32\AMD\xrt-smi.exe.
        # shutil.which honours PATH but not these standard alt locations.
        for alt in (r"C:\Windows\System32\AMD\xrt-smi.exe",
                    r"C:\Program Files\AMD\xrt-smi.exe"):
            if os.path.isfile(alt):
                exe = alt
                break
    if exe:
        try:
            out = subprocess.run(
                [exe, "examine"], capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            # xrt-smi output starts with the XRT board, not the GPU. Look
            # for an AMD Radeon line instead.
            for line in out.splitlines():
                stripped = line.strip()
                if "AMD Radeon" in stripped and "Memory" in stripped:
                    name = stripped.split(":", 1)[1].strip()
                    mib = _amd_total_memory_from_xrt(out)
                    if mib > 0:
                        return GPU(name=name, vram_mib=mib, driver="0.0", is_amd=True)
        except (OSError, subprocess.SubprocessError):
            pass

    # Tier 3: WMI. Always available on Windows; cheap subprocess call.
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-WmiObject Win32_VideoController | "
             "Where-Object { $_.VideoProcessor -like '*AMD*' -or "
             "$_.AdapterCompatibility -like '*AMD*' -or $_.Name -like '*AMD*' -or "
             "$_.Name -like '*Radeon*' } | "
             "Select-Object Name, AdapterRAM, AdapterCompatibility | "
             "ConvertTo-Csv -NoTypeInformation)"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        for line in out.splitlines()[1:]:  # skip CSV header
            line = line.strip()
            if not line:
                continue
            # CSV format: "Name","AdapterRAM","AdapterCompatibility"
            parts = [p.strip('"') for p in line.split(",", 2)]
            if len(parts) < 3:
                continue
            name, ram_str, _compat = parts
            if not name or "Radeon" not in name and "AMD" not in name:
                continue
            # WMI AdapterRAM is reported in bytes for the dedicated pool,
            # but Windows lies - often returns system shared memory (~4 GB).
            # Treat any AMD positive integer as valid; the verdict does not
            # need precise VRAM to decide "ok" vs "warn".
            try:
                ram = int(ram_str)
            except ValueError:
                ram = 0
            if name and ram > 0:
                return GPU(name=name, vram_mib=ram // (1024 * 1024),
                           driver="0.0", is_amd=True)
    except (OSError, subprocess.SubprocessError):
        pass

    # Tier 4: AMD driver DLL presence as a final hint. The Adrenalin driver
    # ships amdhip64_7.dll to C:\Windows\System32. If that file is there,
    # the box is AMD-equipped even if every CLI tool is missing.
    for dll in (r"C:\Windows\System32\amdhip64_7.dll",
                r"C:\Windows\System32\amdhip64.dll"):
        if os.path.isfile(dll):
            # We have no way to read VRAM. Use a 4 GB fallback so the
            # verdict still classifies the card as "works in low-memory mode"
            # rather than "not enough memory".
            return GPU(name="AMD Radeon (driver only)", vram_mib=4096 * 1024,
                       driver="0.0", is_amd=True)
    return None


def detect() -> GPU | None:
    """The largest GPU, regardless of vendor. NVIDIA first, AMD second."""
    return _detect_nvidia() or _detect_amd()


#: How hard to lean on the card. The engine always gets the whole card; a mode
#: only switches on savers (see MEMORY_MODES in workers/yue2_worker.py). An
#: earlier design passed "12 GB" as YuE2's memory budget, but that budget is a
#: hard ceiling, so on a 16 GB card it caused the out-of-memory it meant to avoid.
MEMORY_MODES = ("fast", "balanced", "low")


def auto_memory(gpu: GPU | None) -> str:
    """Below 24 GB, Lowest memory. Measured on a 16 GB RTX A4000 with a 3-minute
    song: Balanced peaked at 12.9 GiB (of 14 usable), Lowest memory at 9.5 GiB,
    and Lowest memory was only 4% slower (354 s against 340 s)."""
    if gpu is None or gpu.vram_gib >= 23:
        return "fast"
    return "low"


def verdict(gpu: GPU | None) -> tuple[str, str]:
    """(level, sentence) where level is ok | warn | bad."""
    if gpu is None:
        return "bad", t("No CUDA or ROCm graphics card found - Gokuk needs a GPU to make music.")
    # AMD detection does not surface a driver version; the NVIDIA minimum
    # driver check only applies when one was returned.
    if not gpu.is_amd and gpu.driver_number and gpu.driver_number < MIN_DRIVER:
        return "bad", t("{name}: the NVIDIA graphics driver ({driver}) is too old. Update it from nvidia.com "
                        "to version {need} or newer.", name=gpu.name, driver=gpu.driver,
                        need=int(MIN_DRIVER))
    gib = round(gpu.vram_gib)
    if gpu.vram_gib >= 23:
        return "ok", t("{name} · {gib} GB - full speed.", name=gpu.name, gib=gib)
    if gpu.vram_gib >= 11:
        return "warn", t("{name} · {gib} GB - works in low-memory mode, slower than a 24 GB card.",
                         name=gpu.name, gib=gib)
    return "bad", t("{name} · {gib} GB - not enough graphics memory (12 GB minimum).",
                    name=gpu.name, gib=gib)
