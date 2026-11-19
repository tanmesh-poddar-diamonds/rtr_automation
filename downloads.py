import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SaveResult:
    status: str  # "saved" | "skipped" | "failed"
    name: str
    detail: str = ""


def ring_dir(output_dir: Path | str, key: str, create: bool = True) -> Path:
    folder = Path(output_dir) / key
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def _unique(raw: str, seen: set[str]) -> str:
    stem, suffix = Path(raw).stem, Path(raw).suffix
    name, n = raw, 2
    while name in seen:
        name = f"{stem}__{n}{suffix}"
        n += 1
    return name


def save_download(download, folder: Path, seen: set[str]) -> SaveResult:
    """Save one browser download into `folder`.

    `seen` holds names handled earlier in THIS run, so two images the tool names
    identically are both kept (second gets `__2`). A non-empty file already on disk
    (from an earlier run) is skipped; empty leftovers are re-saved.
    """
    raw = Path(download.suggested_filename).name or "download.bin"
    name = _unique(raw, seen)
    seen.add(name)
    target = Path(folder) / name
    if target.exists() and target.stat().st_size > 0:
        return SaveResult("skipped", name)
    failure = download.failure()
    if failure:
        return SaveResult("failed", name, str(failure))
    part = target.with_name(target.name + ".part")
    try:
        download.save_as(str(part))
        if part.stat().st_size == 0:
            part.unlink()
            return SaveResult("failed", name, "empty file")
        os.replace(part, target)
    except Exception as exc:  # noqa: BLE001 - any save error is a per-file failure
        part.unlink(missing_ok=True)
        return SaveResult("failed", name, str(exc))
    detail = "name collision in this run" if name != raw else ""
    return SaveResult("saved", name, detail)
