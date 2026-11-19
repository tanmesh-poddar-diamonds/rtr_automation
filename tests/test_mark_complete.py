from mark_complete import main, scan


def write_log(logs, key, lines):
    (logs / f"{key}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_ring(out, key, n_images):
    d = out / key
    d.mkdir(parents=True)
    for i in range(n_images):
        (d / f"img-{i}.jpg").write_bytes(b"x" * 10)
    return d


STALLED = ("2026-10-10 00:30:04 | INFO | {k} | finished: stalled (saved {n}, skipped 0, failed 0, 1147s) "
           "no progress for 120s at ({a}, {t})")


def test_stalled_ring_with_every_file_present_is_marked_complete(tmp_path):
    logs, out = tmp_path / "logs", tmp_path / "out"
    logs.mkdir()
    make_ring(out, "A1_PR_1.5", 5)
    write_log(logs, "A1_PR_1.5", ["x | run started", STALLED.format(k="A1_PR_1.5", n=5, a=4, t=5)])
    found = scan(logs, out)
    assert [f.key for f in found] == ["A1_PR_1.5"]
    assert not (out / "A1_PR_1.5" / ".complete").exists()   # scan alone changes nothing


def test_apply_writes_marker_and_is_repeatable(tmp_path):
    logs, out = tmp_path / "logs", tmp_path / "out"
    logs.mkdir()
    make_ring(out, "A1_PR_1.5", 5)
    write_log(logs, "A1_PR_1.5", [STALLED.format(k="A1_PR_1.5", n=5, a=4, t=5)])
    assert main(["--log-dir", str(logs), "--output-dir", str(out), "--apply"]) == 0
    assert (out / "A1_PR_1.5" / ".complete").exists()
    assert scan(logs, out) == []          # already marked: nothing left to repair


def test_missing_files_or_genuine_stalls_are_not_marked(tmp_path):
    logs, out = tmp_path / "logs", tmp_path / "out"
    logs.mkdir()
    make_ring(out, "SHORT_PR_1.5", 3)     # only 3 of 5 files on disk
    write_log(logs, "SHORT_PR_1.5", [STALLED.format(k="SHORT_PR_1.5", n=5, a=4, t=5)])
    make_ring(out, "HALF_PR_1.5", 2)      # stalled halfway
    write_log(logs, "HALF_PR_1.5", [STALLED.format(k="HALF_PR_1.5", n=2, a=2, t=5)])
    assert scan(logs, out) == []


def test_only_the_latest_run_in_an_appended_log_counts(tmp_path):
    logs, out = tmp_path / "logs", tmp_path / "out"
    logs.mkdir()
    make_ring(out, "A1_PR_1.5", 5)
    write_log(logs, "A1_PR_1.5", [
        STALLED.format(k="A1_PR_1.5", n=5, a=4, t=5),
        "x | run started",
        "2026-10-11 | INFO | A1_PR_1.5 | finished: failed (saved 0, skipped 0, failed 0, 5s) viewer",
    ])
    assert scan(logs, out) == []


def test_partial_and_failed_rings_are_never_marked(tmp_path):
    logs, out = tmp_path / "logs", tmp_path / "out"
    logs.mkdir()
    make_ring(out, "P1_PR_1.5", 5)
    write_log(logs, "P1_PR_1.5", ["x | INFO | P1 | finished: partial (saved 5, skipped 0, failed 1, 9s) boom"])
    assert scan(logs, out) == []
