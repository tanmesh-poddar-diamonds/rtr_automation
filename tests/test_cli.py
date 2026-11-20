import csv

from rtr_run import main
from tests.fakes import Clock, FakeDownload, FakeDriver, driver_factory

ENV = {"BASE_URL": "https://h/p?SID=secret&mode=ring_3_d&sub=admin_panel&d=X"}


def setup_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("rtr_run.load_dotenv", lambda *a, **k: None)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


def test_full_cli_run_writes_summary_logs_and_invalid_rows(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text("sku,shape,carat\nA1,Pear,1.5\nB2,Cushion,1\n", encoding="utf-8")
    clock = Clock()
    drv = FakeDriver(clock, steps=[((1, 1), [FakeDownload("x.jpg")])])
    code = main(["rings.csv"], open_driver_factory=lambda cfg: (lambda: driver_factory(drv)))
    assert code == 1  # one invalid row
    rows = list(csv.DictReader((tmp_path / "summary.csv").open(encoding="utf-8")))
    assert [(r["sku"], r["status"]) for r in rows] == [("A1", "done"), ("B2", "invalid")]
    assert (tmp_path / "output" / "A1" / "x.jpg").exists()
    assert (tmp_path / "logs" / "A1_PR_1.5.log").exists()
    assert "secret" not in (tmp_path / "logs" / "_run.log").read_text(encoding="utf-8")


def test_missing_base_url_is_config_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("rtr_run.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("BASE_URL", raising=False)
    (tmp_path / "rings.csv").write_text("sku,shape,carat\nA1,Pear,1\n", encoding="utf-8")
    assert main(["rings.csv"]) == 2


def test_bad_csv_header_is_config_error(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text("sku,shape\nA1,Pear\n", encoding="utf-8")
    assert main(["rings.csv"]) == 2


def test_limit_runs_only_first_n_rings(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text("sku,shape,carat\nA1,Pear,1\nA2,Pear,1\n", encoding="utf-8")
    clock = Clock()
    drivers = iter([FakeDriver(clock, steps=[((1, 1), [FakeDownload("x.jpg")])])])
    code = main(["rings.csv", "--limit", "1"],
                open_driver_factory=lambda cfg: (lambda: driver_factory(next(drivers))))
    assert code == 0
    rows = list(csv.DictReader((tmp_path / "summary.csv").open(encoding="utf-8")))
    assert [r["sku"] for r in rows] == ["A1"]


def test_second_cli_run_skips_finished_rings_and_force_rebuilds(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text("sku,shape,carat\nA1,Pear,1.5\n", encoding="utf-8")

    def run(extra=()):
        clock = Clock()
        drv = FakeDriver(clock, steps=[((1, 1), [FakeDownload("x.jpg")])])
        return main(["rings.csv", *extra],
                    open_driver_factory=lambda cfg: (lambda: driver_factory(drv)))

    def statuses():
        return [r["status"] for r in csv.DictReader((tmp_path / "summary.csv").open(encoding="utf-8"))]

    assert run() == 0 and statuses() == ["done"]
    assert run() == 0 and statuses() == ["skipped"]
    assert run(["--force"]) == 0 and statuses() == ["done"]


def test_shard_runs_only_its_skus_and_uses_its_own_summary_and_run_log(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text(
        "sku,shape,carat\nA1,Pear,1.5\nB2,Pear,1.5\nB2,Round,1.5\n", encoding="utf-8")
    clock = Clock()
    drivers = iter([FakeDriver(clock, steps=[((1, 1), [FakeDownload("x.jpg")])]),
                    FakeDriver(clock, steps=[((1, 1), [FakeDownload("y.jpg")])])])
    code = main(["rings.csv", "--shard", "2/2"],
                open_driver_factory=lambda cfg: (lambda: driver_factory(next(drivers))))
    assert code == 0
    rows = list(csv.DictReader((tmp_path / "summary_shard_2.csv").open(encoding="utf-8")))
    assert [(r["sku"], r["shape"]) for r in rows] == [("B2", "Pear"), ("B2", "Round")]
    assert not (tmp_path / "summary.csv").exists()
    assert (tmp_path / "logs" / "_run_shard2.log").exists()
    assert not (tmp_path / "output" / "A1").exists()


def test_bad_shard_value_is_a_config_error(tmp_path, monkeypatch):
    setup_env(monkeypatch, tmp_path)
    (tmp_path / "rings.csv").write_text("sku,shape,carat\nA1,Pear,1.5\n", encoding="utf-8")
    assert main(["rings.csv", "--shard", "9/2"]) == 2
