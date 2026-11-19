"""Repair tool: give the .complete marker to rings that really finished.

Older runs judged a ring "done" by its counter, which stops one short of the total, so finished
rings were logged as `stalled` and never marked. A ring qualifies when its latest log line says
`finished: stalled` at counter (n, TOTAL) AND its folder holds at least TOTAL image files.
Dry run by default; pass --apply to write the markers.
"""
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_AT = re.compile(r"no progress for \d+s at \((\d+), (\d+)\)")


@dataclass(frozen=True)
class Candidate:
    key: str
    total: int
    files: int


def _latest_finished(log_path: Path) -> str | None:
    last = None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "| finished: " in line:
            last = line
    return last


def _count_images(folder: Path) -> int:
    return sum(1 for f in folder.iterdir()
               if f.is_file() and not f.name.startswith(".") and not f.name.endswith(".part"))


def scan(log_dir: Path | str, output_dir: Path | str) -> list[Candidate]:
    found: list[Candidate] = []
    for log_path in sorted(Path(log_dir).glob("*.log")):
        if log_path.name.startswith("_"):
            continue
        key = log_path.stem
        folder = Path(output_dir) / key
        if not folder.is_dir() or (folder / ".complete").exists():
            continue
        line = _latest_finished(log_path)
        if not line or "finished: stalled" not in line:
            continue
        m = _AT.search(line)
        if not m:
            continue
        total = int(m.group(2))
        files = _count_images(folder)
        if total > 0 and files >= total:
            found.append(Candidate(key, total, files))
    return found


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Mark rings that really finished as complete.")
    p.add_argument("--log-dir", default="logs")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--apply", action="store_true", help="write the .complete markers")
    args = p.parse_args(argv)
    found = scan(args.log_dir, args.output_dir)
    for c in found:
        if args.apply:
            (Path(args.output_dir) / c.key / ".complete").write_text(
                f"completed (repaired from log: {c.files} files, total {c.total})\n", encoding="utf-8")
    verb = "marked" if args.apply else "would mark"
    print(f"{verb} {len(found)} ring(s) as complete" + ("" if args.apply else " (dry run; add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
