# RTR images automation

Reads `rings.csv` (`sku, shape, carat`) and, for each row, opens the ring in the RTR admin
panel in a visible Chrome window, opens Script_1, sets Carats and the shape, clicks BUILD and
saves every downloaded image to `output/<SKU>_<CODE>/`.

## Setup
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and paste your admin-panel URL (with `SID=`) into `BASE_URL`.
3. Edit `rings.csv`.

## Run
    python rtr_run.py rings.csv
    python rtr_run.py rings.csv --max-images 5     # smoke test: stop each ring after 5 images
    python rtr_run.py rings.csv --limit 1          # only the first row

Re-running resumes: files that already exist in a ring's folder are not saved again
(the tool still re-renders them).

## Output
- `output/<SKU>_<CODE>/` images with the tool's own filenames
- `logs/<SKU>_<CODE>.log` per-ring log; `logs/_run.log` batch log (session id masked)
- `summary.csv` one row per ring: status, downloaded, skipped, failed, seconds

Statuses: done, partial, stalled, failed, not_found, invalid. Exit code 0 = everything done.
Stop with Ctrl+C: the current ring is recorded as `partial` and a summary is written.
