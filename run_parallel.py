import argparse
import subprocess
import sys
from pathlib import Path

from shards import build_commands, merge_summaries


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Run rtr_run.py in several console windows at once, one slice of SKUs each. "
                    "Unrecognised options (--max-images, --limit, --force ...) go to every worker.")
    p.add_argument("csv")
    p.add_argument("--workers", type=int, default=10)
    args, extra = p.parse_known_args(argv)
    if args.workers < 1:
        print("--workers must be at least 1", file=sys.stderr)
        return 2
    commands = build_commands(args.csv, args.workers, extra)
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    procs = []
    for i, cmd in enumerate(commands, 1):
        print(f"starting worker {i}/{args.workers}", flush=True)
        procs.append(subprocess.Popen(cmd, creationflags=flags))
    try:
        codes = [proc.wait() for proc in procs]
    except KeyboardInterrupt:
        print("Ctrl+C: stopping workers", flush=True)
        for proc in procs:
            proc.terminate()
        codes = [proc.wait() for proc in procs]
    n = merge_summaries([f"summary_shard_{i}.csv" for i in range(1, args.workers + 1)],
                        "summary_all.csv")
    print(f"workers finished, exit codes {codes}; {n} ring(s) merged into summary_all.csv")
    return max(codes)


if __name__ == "__main__":
    sys.exit(main())
