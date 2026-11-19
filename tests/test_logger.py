from logger import mask_sid, ring_logger, setup_logging

SECRET = "q6cxw3e_260306211847"
URL = f"https://h/p.aspx?SID={SECRET}&mode=ring_3_d"


def test_mask_sid():
    assert mask_sid(URL) == "https://h/p.aspx?SID=***&mode=ring_3_d"


def test_each_ring_gets_its_own_file_and_lines_do_not_leak(tmp_path):
    setup_logging(tmp_path)
    with ring_logger(tmp_path, "AAA_PR") as a:
        a.info("hello from a")
    with ring_logger(tmp_path, "BBB_RD") as b:
        b.info("hello from b")
    ta = (tmp_path / "AAA_PR.log").read_text(encoding="utf-8")
    tb = (tmp_path / "BBB_RD.log").read_text(encoding="utf-8")
    assert "hello from a" in ta and "hello from b" not in ta
    assert "hello from b" in tb and "hello from a" not in tb
    assert "| INFO | AAA_PR | hello from a" in ta


def test_rerun_appends_with_run_started_marker(tmp_path):
    setup_logging(tmp_path)
    for _ in range(2):
        with ring_logger(tmp_path, "AAA_PR") as a:
            a.info("x")
    text = (tmp_path / "AAA_PR.log").read_text(encoding="utf-8")
    assert text.count("run started") == 2


def test_sid_is_masked_in_message_and_traceback(tmp_path):
    setup_logging(tmp_path)
    with ring_logger(tmp_path, "AAA_PR") as a:
        a.info("opening %s", URL)
        try:
            raise RuntimeError(f"goto failed for {URL}")
        except RuntimeError:
            a.exception("boom")
    text = (tmp_path / "AAA_PR.log").read_text(encoding="utf-8")
    assert SECRET not in text
    assert text.count("SID=***") >= 2  # the info line and the exception message in the traceback


def test_run_log_written(tmp_path):
    run = setup_logging(tmp_path)
    run.info("batch started")
    assert "batch started" in (tmp_path / "_run.log").read_text(encoding="utf-8")


def test_run_log_file_name_can_be_chosen_per_worker(tmp_path):
    run = setup_logging(tmp_path, run_log_name="_run_shard3.log")
    run.info("worker three")
    assert "worker three" in (tmp_path / "_run_shard3.log").read_text(encoding="utf-8")
    assert not (tmp_path / "_run.log").exists()
