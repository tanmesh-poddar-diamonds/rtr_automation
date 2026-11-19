import logging

from config import Config
from downloads import ring_dir
from rings_csv import RingRequest
from runner import run_batch, run_ring
from tests.fakes import Clock, FakeDownload, FakeDriver, driver_factory

LOG = logging.getLogger("test-runner")


def cfg(tmp_path, stall=5):
    return Config("https://h/p?SID=s", tmp_path / "out", tmp_path / "logs",
                  stall, 1, "chrome", False, "833")


def req(sku="A1", shape="Pear", code="PR"):
    return RingRequest(sku, shape, code, "1.5", f"833-{sku}-not_resizable_{code}-0.00-01", f"{sku}_{code}")


def dl(n):
    return FakeDownload(f"img-{n}.jpg")


def test_happy_path_done_and_panel_configured_in_order(tmp_path):
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 3), [dl(1)]), ((2, 3), [dl(2)]), ((3, 3), [dl(3)])])
    res = run_ring(req(), drv, cfg(tmp_path), LOG, now=clock)
    assert (res.status, res.downloaded, res.skipped, res.failed) == ("done", 3, 0, 0)
    names = [c[0] for c in drv.calls]
    assert names == ["open_ring", "open_panel", "set_carat", "select_only_shape",
                     "ensure_all_colours", "start_build"]
    assert ("set_carat", "1.5") in drv.calls and ("select_only_shape", "Pear") in drv.calls
    folder = tmp_path / "out" / "A1_PR"
    assert sorted(p.name for p in folder.iterdir() if p.suffix == ".jpg") == ["img-1.jpg", "img-2.jpg", "img-3.jpg"]
    assert (folder / ".complete").exists()


def test_not_found(tmp_path):
    clock = Clock()
    res = run_ring(req(), FakeDriver(clock, found=False), cfg(tmp_path), LOG, now=clock)
    assert res.status == "not_found"


def test_open_is_retried_once_then_fails(tmp_path):
    clock = Clock()
    ok = FakeDriver(clock, steps=[((1, 1), [dl(1)])], open_failures=1)
    assert run_ring(req(), ok, cfg(tmp_path), LOG, now=clock).status == "done"
    bad = FakeDriver(Clock(), open_failures=2)
    res = run_ring(req("B1"), bad, cfg(tmp_path), LOG, now=bad.clock)
    assert res.status == "failed" and "panel did not open" in res.message


def test_stall_clicks_stop_and_reports_stalled(tmp_path):
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 10), [dl(1)])])
    res = run_ring(req(), drv, cfg(tmp_path, stall=5), LOG, now=clock)
    assert res.status == "stalled" and res.downloaded == 1
    assert ("stop_build",) in drv.calls


def test_resume_skips_existing_files(tmp_path):
    folder = ring_dir(tmp_path / "out", "A1_PR")
    (folder / "img-1.jpg").write_bytes(b"already here")
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 2), [dl(1)]), ((2, 2), [dl(2)])])
    res = run_ring(req(), drv, cfg(tmp_path), LOG, now=clock)
    assert (res.status, res.downloaded, res.skipped) == ("done", 1, 1)


def test_failed_file_makes_ring_partial(tmp_path):
    clock = Clock()
    bad = FakeDownload("img-2.jpg", failure="canceled")
    drv = FakeDriver(clock, steps=[((1, 2), [dl(1)]), ((2, 2), [bad])])
    res = run_ring(req(), drv, cfg(tmp_path), LOG, now=clock)
    assert (res.status, res.downloaded, res.failed) == ("partial", 1, 1)


def test_max_images_stops_build_and_is_partial(tmp_path):
    clock = Clock()
    drv = FakeDriver(clock, steps=[((i, 99), [dl(i)]) for i in range(1, 50)])
    res = run_ring(req(), drv, cfg(tmp_path), LOG, now=clock, max_images=3)
    assert res.status == "partial" and res.downloaded >= 3 and "max-images" in res.message
    assert ("stop_build",) in drv.calls


def test_unexpected_exception_after_progress_is_partial_not_crash(tmp_path):
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 3), [dl(1)])])
    drv.read_progress_orig = drv.read_progress

    def boom():
        if not drv.steps:
            raise RuntimeError("browser died")
        return drv.read_progress_orig()
    drv.read_progress = boom
    res = run_ring(req(), drv, cfg(tmp_path), LOG, now=clock)
    assert res.status == "partial" and "browser died" in res.message and res.downloaded == 1


def test_batch_continues_after_a_bad_ring_and_writes_per_ring_logs(tmp_path):
    clock = Clock()
    good = FakeDriver(clock, steps=[((1, 1), [dl(1)])])
    drivers = iter([FakeDriver(clock, found=False), good])
    results, stop = run_batch(
        [req("A1"), req("B1")], lambda: driver_factory(next(drivers)), cfg(tmp_path),
        LOG, now=clock)
    assert [r.status for r in results] == ["not_found", "done"] and stop is None
    assert (tmp_path / "logs" / "A1_PR.log").exists() and (tmp_path / "logs" / "B1_PR.log").exists()


def test_ctrl_c_stops_batch_with_partial_result(tmp_path):
    clock = Clock()
    first = FakeDriver(clock, build_raises=KeyboardInterrupt())
    second = FakeDriver(clock, steps=[((1, 1), [dl(1)])])
    drivers = iter([first, second])
    results, stop = run_batch(
        [req("A1"), req("B1")], lambda: driver_factory(next(drivers)), cfg(tmp_path),
        LOG, now=clock)
    assert stop == "interrupted"
    assert len(results) == 1 and results[0].status == "partial" and results[0].interrupted
    assert ("open_ring", "833-B1-not_resizable_PR-0.00-01") not in second.calls


def test_done_ring_writes_marker_and_second_run_is_skipped_without_touching_the_browser(tmp_path):
    clock = Clock()
    first = FakeDriver(clock, steps=[((1, 1), [dl(1)])])
    assert run_ring(req(), first, cfg(tmp_path), LOG, now=clock).status == "done"
    assert (tmp_path / "out" / "A1_PR" / ".complete").exists()
    second = FakeDriver(clock, steps=[((1, 1), [dl(1)])])
    res = run_ring(req(), second, cfg(tmp_path), LOG, now=clock)
    assert res.status == "skipped" and "already complete" in res.message
    assert second.calls == []


def test_unfinished_rings_never_get_the_marker(tmp_path):
    clock = Clock()
    stalled = FakeDriver(clock, steps=[((1, 10), [dl(1)])])
    assert run_ring(req("S1"), stalled, cfg(tmp_path, stall=5), LOG, now=clock).status == "stalled"
    limited = FakeDriver(clock, steps=[((i, 99), [dl(i)]) for i in range(1, 50)])
    assert run_ring(req("L1"), limited, cfg(tmp_path), LOG, now=clock, max_images=2).status == "partial"
    killed = FakeDriver(clock, build_raises=KeyboardInterrupt())
    assert run_ring(req("K1"), killed, cfg(tmp_path), LOG, now=clock).interrupted
    for sku in ("S1", "L1", "K1"):
        assert not (tmp_path / "out" / f"{sku}_PR" / ".complete").exists()


def test_force_rebuilds_a_complete_ring_and_drops_a_stale_marker_if_it_fails(tmp_path):
    clock = Clock()
    run_ring(req(), FakeDriver(clock, steps=[((1, 1), [dl(1)])]), cfg(tmp_path), LOG, now=clock)
    marker = tmp_path / "out" / "A1_PR" / ".complete"
    assert marker.exists()
    ok = FakeDriver(clock, steps=[((1, 1), [dl(1)])])
    assert run_ring(req(), ok, cfg(tmp_path), LOG, now=clock, force=True).status == "done"
    assert ("start_build",) in ok.calls and marker.exists()
    bad = FakeDriver(clock, steps=[((1, 10), [dl(1)])])
    assert run_ring(req(), bad, cfg(tmp_path, stall=5), LOG, now=clock, force=True).status == "stalled"
    assert not marker.exists()


def test_ring_is_done_when_files_reach_the_total_even_though_the_counter_stops_one_short(tmp_path):
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 5), [dl(1)]), ((2, 5), [dl(2)]), ((3, 5), [dl(3)]),
                                   ((4, 5), [dl(4), dl(5)])])  # the counter never reaches 5
    res = run_ring(req(), drv, cfg(tmp_path, stall=5), LOG, now=clock)
    assert (res.status, res.downloaded) == ("done", 5)
    assert ("stop_build",) not in drv.calls
    assert (tmp_path / "out" / "A1_PR" / ".complete").exists()


def test_a_ring_that_never_opens_leaves_no_folder_behind(tmp_path):
    clock = Clock()
    assert run_ring(req(), FakeDriver(clock, found=False), cfg(tmp_path), LOG, now=clock).status == "not_found"
    assert run_ring(req("B1"), FakeDriver(clock, open_failures=2), cfg(tmp_path), LOG, now=clock).status == "failed"
    assert not (tmp_path / "out" / "A1_PR").exists()
    assert not (tmp_path / "out" / "B1_PR").exists()


def test_batch_stops_after_consecutive_failures_instead_of_burning_hours(tmp_path):
    clock = Clock()
    drivers = iter([FakeDriver(clock, open_failures=2) for _ in range(5)])
    results, stop = run_batch(
        [req(f"S{i}") for i in range(5)], lambda: driver_factory(next(drivers)), cfg(tmp_path),
        LOG, now=clock, max_consecutive_failures=2)
    assert stop == "unhealthy" and [r.status for r in results] == ["failed", "failed"]


def test_a_good_ring_resets_the_failure_streak(tmp_path):
    clock = Clock()
    seq = iter([FakeDriver(clock, open_failures=2),
                FakeDriver(clock, steps=[((1, 1), [dl(1)])]),
                FakeDriver(clock, open_failures=2),
                FakeDriver(clock, steps=[((1, 1), [dl(2)])])])
    results, stop = run_batch(
        [req(f"S{i}") for i in range(4)], lambda: driver_factory(next(seq)), cfg(tmp_path),
        LOG, now=clock, max_consecutive_failures=2)
    assert stop is None and [r.status for r in results] == ["failed", "done", "failed", "done"]


def test_not_found_rings_do_not_count_as_failures(tmp_path):
    clock = Clock()
    drivers = iter([FakeDriver(clock, found=False) for _ in range(4)])
    results, stop = run_batch(
        [req(f"S{i}") for i in range(4)], lambda: driver_factory(next(drivers)), cfg(tmp_path),
        LOG, now=clock, max_consecutive_failures=2)
    assert stop is None and len(results) == 4


def test_zero_disables_the_failure_limit(tmp_path):
    clock = Clock()
    drivers = iter([FakeDriver(clock, open_failures=2) for _ in range(3)])
    results, stop = run_batch(
        [req(f"S{i}") for i in range(3)], lambda: driver_factory(next(drivers)), cfg(tmp_path),
        LOG, now=clock, max_consecutive_failures=0)
    assert stop is None and len(results) == 3
