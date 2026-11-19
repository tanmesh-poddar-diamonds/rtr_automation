import csv

import pytest

from rings_csv import RingRequest
from shards import build_commands, merge_summaries, parse_shard, select_shard


def r(sku, shape="Pear", carat="1.5"):
    return RingRequest(sku, shape, "PR", carat, "label", f"{sku}_PR_{carat}")


def test_parse_shard():
    assert parse_shard("3/10") == (3, 10)
    assert parse_shard(" 1/1 ") == (1, 1)


@pytest.mark.parametrize("bad", ["0/10", "11/10", "3", "a/b", "3/0", "-1/4", ""])
def test_parse_shard_rejects_bad_values(bad):
    with pytest.raises(ValueError, match="shard"):
        parse_shard(bad)


def test_select_shard_groups_by_sku_round_robin():
    reqs = [r("A"), r("A", "Round"), r("B"), r("B", "Round"), r("C"), r("D")]
    assert [x.key for x in select_shard(reqs, 1, 2)] == ["A_PR_1.5", "A_PR_1.5", "C_PR_1.5"]
    assert [x.sku for x in select_shard(reqs, 2, 2)] == ["B", "B", "D"]


def test_every_request_lands_in_exactly_one_shard_and_a_sku_never_splits():
    reqs = [r(f"S{i % 7}", carat=str(1 + i)) for i in range(40)]
    parts = [select_shard(reqs, i, 10) for i in range(1, 11)]
    assert sorted(x.key for p in parts for x in p) == sorted(x.key for x in reqs)
    owner = {}
    for i, p in enumerate(parts):
        for x in p:
            assert owner.setdefault(x.sku, i) == i


def test_more_workers_than_skus_leaves_some_shards_empty():
    reqs = [r("A"), r("B")]
    assert select_shard(reqs, 5, 10) == []


def test_build_commands_one_per_worker_with_passthrough_args():
    cmds = build_commands("rings.csv", 3, ["--max-images", "5"], python="py", script="rtr_run.py")
    assert cmds == [
        ["py", "rtr_run.py", "rings.csv", "--shard", f"{i}/3", "--max-images", "5"] for i in (1, 2, 3)
    ]


def test_merge_summaries_keeps_one_header_and_skips_missing_files(tmp_path):
    cols = ["sku", "shape", "carat", "status", "downloaded", "skipped", "failed", "seconds"]
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    for path, sku in ((a, "A1"), (b, "B1")):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerow([sku, "Pear", "1.5", "done", 1, 0, 0, "1.0"])
    out = tmp_path / "all.csv"
    merge_summaries([a, tmp_path / "missing.csv", b], out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [x["sku"] for x in rows] == ["A1", "B1"]
    assert out.read_text(encoding="utf-8").count("sku,shape") == 1
