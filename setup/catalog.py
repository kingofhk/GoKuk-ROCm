"""What Gokuk Setup can install, read from setup/catalog.json.

The catalogue is written by tools/build_manifest.py and ships with the
program. Every download in it is pinned - a URL, a size, and a sha256 - so a
Setup run today fetches exactly the bytes the release was tested with.

Four kinds of item:

* ``model``   - a HuggingFace repository at a fixed commit, as a list of files.
* ``archive`` - a zip or tar.gz unpacked into a folder (uv, Python, FFmpeg).
* ``wheels``  - one Python environment: wheels downloaded one by one, then
  installed offline into that environment's standalone Python.

Items belong to a component (Song creation, Cover maker, ...). The window works
in components; the installer works in items.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.paths import resource_dir

CATALOG_PATH = resource_dir() / "setup" / "catalog.json"


@dataclass
class Component:
    id: str
    label: str
    detail: str
    required: bool
    default: bool


@dataclass
class Item:
    id: str
    kind: str                 # model | archive | wheels
    component: str
    size: int
    data: dict = field(repr=False)

    @property
    def dest(self) -> str:
        return self.data.get("dest", "")

    @property
    def vendor(self) -> str:
        """``amd`` for ROCm-only items, ``nvidia`` for the rest. Defaults to
        ``nvidia`` so the existing catalog is unaffected."""
        return self.data.get("vendor", "nvidia")

    @property
    def files(self) -> list[dict]:
        """(url, relative target, size, sha256) for everything this item downloads."""
        if self.kind == "model":
            return [{"url": f["url"], "target": f"{self.dest}/{f['path']}",
                     "size": f["size"], "sha256": f.get("sha256", "")}
                    for f in self.data["files"]]
        if self.kind == "archive":
            name = self.data["url"].rsplit("/", 1)[-1].replace("%2B", "+")
            return [{"url": self.data["url"], "target": f"cache/downloads/{name}",
                     "size": self.size, "sha256": self.data["sha256"]}]
        if self.kind == "wheels":
            return [{"url": w["url"], "target": f"cache/wheels/{w['url'].rsplit('/', 1)[-1].replace('%2B', '+')}",
                     "size": w["size"], "sha256": w["sha256"]}
                    for w in self.data["wheels"]]
        return []

    @property
    def label(self) -> str:
        kind, _, name = self.id.partition(":")
        return {"model": name, "python": f"Python ({name})", "env": f"Libraries ({name})",
                "tool": name}.get(kind, self.id)


class Catalog:
    def __init__(self, path: Path | str = CATALOG_PATH):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.components = [Component(c["id"], c["label"], c.get("detail", ""),
                                      bool(c.get("required")), bool(c.get("default")))
                           for c in raw["components"]]
        self.items = [Item(i["id"], i["kind"], i["component"], int(i["size"]), i)
                      for i in raw["items"]]

    def component(self, cid: str) -> Component:
        return next(c for c in self.components if c.id == cid)

    def items_for(self, components, vendor: str = "nvidia") -> list[Item]:
        """Items belonging to the requested components AND matching the vendor.

        ``vendor`` defaults to ``"nvidia"`` so the existing call sites keep
        their behaviour. Pass ``"amd"`` to switch to the ROCm-only wheel set;
        models are vendor-neutral and are included by either choice.
        """
        wanted = set(components) | {c.id for c in self.components if c.required}
        result = []
        for item in self.items:
            if item.component not in wanted:
                continue
            # Models are vendor-neutral: they hold safetensors + config that
            # both NVIDIA and AMD runtimes can load.
            if item.kind == "model":
                result.append(item)
                continue
            if item.vendor == vendor:
                result.append(item)
        return result

    def download_bytes(self, components, vendor: str = "nvidia") -> int:
        return sum(i.size for i in self.items_for(components, vendor))

    def component_bytes(self, cid: str, vendor: str = "nvidia") -> int:
        items = self.items_for([cid], vendor)
        return sum(i.size for i in items)


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"
