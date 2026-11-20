# RTR images automation

Reads a CSV (`sku, shape, carat`) and, for each row, opens the ring in the RTR admin panel in a
headless Chrome (no window; set `HEADLESS=false` in `.env` to watch it), opens Script_1, sets Carats
and the shape, clicks BUILD and saves every downloaded image to `output/<SKU>/`.

All rings of one SKU (every carat / shape) share a single folder named after the SKU.

## Setup (one PC)
1. Install Python 3.11+ and Google Chrome (the tool drives the installed Chrome, `BROWSER_CHANNEL=chrome`).
2. In the project folder, create the environment and install the packages:

        python -m venv .venv
        .venv\Scripts\activate
        pip install -r requirements.txt

3. Copy `.env.example` to `.env` and paste your admin-panel URL (with `SID=`) into `BASE_URL`.
4. Put your CSV in the folder (columns `sku, shape, carat`).

## Run
    python rtr_run.py rings.csv
    python rtr_run.py rings.csv --max-images 5     # smoke test: stop each ring after 5 images
    python rtr_run.py rings.csv --limit 1          # only the first row
    python rtr_run.py rings.csv --force            # rebuild rings already marked complete

Re-running resumes: rings already finished are skipped, and files that already exist in the SKU
folder are not saved again (the tool still re-renders them).

## Running on 10 PCs
The CSV is split into 10 parts in `rings_split/` (`rings_part_1.csv` ... `rings_part_10.csv`).
A SKU is never divided between parts, so two PCs never write to the same SKU folder. PC *N* runs part *N*.

### Files to copy to every PC
Copy these into one folder on each PC (leave out `.venv`, `logs/`, `output/`, `tests/`):

- Python files: `rtr_run.py`, `config.py`, `logger.py`, `report.py`, `rings_csv.py`, `shapes.py`,
  `runner.py`, `downloads.py`, `rtr_page.py`, `shards.py`
- `requirements.txt`, `.env` (or `.env.example` to fill in)
- `rings_split/rings_part_N.csv` (only that PC's part is needed)

### Setup on each PC
1. Install Python 3.11+ and Google Chrome. Check with `python --version`.
2. Open PowerShell in the project folder and run:

        python -m venv .venv
        .venv\Scripts\activate
        pip install -r requirements.txt

3. Make sure `.env` exists with a valid `BASE_URL` (including `SID=`). Keep `HEADLESS=true` for unattended runs.
4. Smoke test (a few images, one ring):

        python rtr_run.py rings_split\rings_part_N.csv --limit 1 --max-images 3 --summary smoke_summary.csv

   Check that `output/<SKU>/` has images. A `--max-images` run is marked `partial` and gets no
   completion marker, so the real run later rebuilds that ring and keeps the images already saved.

### Run on PC N
    .venv\Scripts\activate
    python rtr_run.py rings_split\rings_part_N.csv --summary summary_part_N.csv

For example PC 3: `python rtr_run.py rings_split\rings_part_3.csv --summary summary_part_3.csv`.
Do not use `--shard` with a part file (the split is already done). If a run stops or the PC restarts,
run the same command again: finished rings are skipped.

### After the runs
- Copy each PC's `output/` contents into one common folder. Each SKU exists on only one PC, so the folders never collide.
- Collect `summary_part_1.csv` ... `summary_part_10.csv` (and `logs/` if you need to investigate failures).

### Checklist and cautions
- One PC per part file; never run the same part on two PCs.
- The `SID` in `BASE_URL` is a session id and may expire; if rings start failing or `not_found`, get a fresh URL and update `.env`.
- Keep `.env` private; it contains the session id.
- Check the output of the first SKU that has several carats: image names must not repeat between carats,
  otherwise a later carat would treat the earlier file as "already exists" and skip it.

### Alternative: one big CSV on every PC
Copy the full `rings.csv` to each PC instead and run `python rtr_run.py rings.csv --shard N/10`.
It gives the same SKU distribution (and writes `summary_shard_N.csv`, `logs/_run_shardN.log`).

## Output
- `output/<SKU>/` images with the tool's own filenames, plus hidden `.complete_<SKU>_<CODE>_<carat>`
  markers (one per finished ring; they let a re-run skip finished rings)
- `logs/<SKU>_<CODE>_<carat>.log` per-ring log; `logs/_run.log` batch log (session id masked)
- `summary.csv` one row per ring: status, downloaded, skipped, failed, seconds

Statuses: done, partial, stalled, failed, not_found, invalid. Exit code 0 = everything done.
Stop with Ctrl+C: the current ring is recorded as `partial` and a summary is written.
