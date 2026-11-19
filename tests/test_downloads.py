from downloads import ring_dir, save_download
from tests.fakes import FakeDownload


def test_ring_dir_created(tmp_path):
    d = ring_dir(tmp_path / "out", "AAA_PR")
    assert d.is_dir() and d.name == "AAA_PR"


def test_saved_then_skipped_on_rerun(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    r1 = save_download(FakeDownload("white-gold-1.jpg"), folder, set())
    assert r1.status == "saved" and (folder / "white-gold-1.jpg").read_bytes() == b"0123456789"
    r2 = save_download(FakeDownload("white-gold-1.jpg"), folder, set())  # new run: fresh `seen`
    assert r2.status == "skipped"


def test_same_name_twice_in_one_run_is_not_dropped(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    seen = set()
    a = save_download(FakeDownload("x.jpg", b"AAAAAAAAAA"), folder, seen)
    b = save_download(FakeDownload("x.jpg", b"BBBBBBBBBB"), folder, seen)
    assert (a.status, b.status) == ("saved", "saved")
    assert b.name == "x__2.jpg"
    assert (folder / "x.jpg").read_bytes() == b"AAAAAAAAAA"
    assert (folder / "x__2.jpg").read_bytes() == b"BBBBBBBBBB"


def test_zero_byte_leftover_is_resaved_not_skipped(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    (folder / "x.jpg").write_bytes(b"")
    (folder / "x.jpg.part").write_bytes(b"stale")
    r = save_download(FakeDownload("x.jpg"), folder, set())
    assert r.status == "saved"
    assert (folder / "x.jpg").stat().st_size == 10
    assert not (folder / "x.jpg.part").exists()


def test_failed_download_reported(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    r = save_download(FakeDownload("x.jpg", failure="canceled"), folder, set())
    assert r.status == "failed" and "canceled" in r.detail
    assert not (folder / "x.jpg").exists()


def test_empty_download_is_failed_and_leaves_nothing(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    r = save_download(FakeDownload("x.jpg", data=b""), folder, set())
    assert r.status == "failed" and "empty" in r.detail
    assert list(folder.iterdir()) == []


def test_path_traversal_in_suggested_name_is_flattened(tmp_path):
    folder = ring_dir(tmp_path, "AAA_PR")
    r = save_download(FakeDownload("../../evil.jpg"), folder, set())
    assert r.status == "saved" and r.name == "evil.jpg"
    assert (folder / "evil.jpg").exists()
