#!/usr/bin/env python3
"""Acquire FRED series (keyless) for Directive #9 D9-C.

The authoritative D9-C design requires FRED macro series alongside the equity
underlyings, and *no API key* is needed for either of these:
  - CSV:      https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>
  - Metadata: https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>&cosd=...

Raw CSVs are written under data/snapshots/<dataset-id>/ (COMMITTED, unlike the
yfinance raw dir) so a snapshot stays recoverable — the D9-A experience showed
that a gitignored-only raw payload cannot be reproduced bit-for-bit later.
Manifests land next to the CSVs.

Network acquisition is for local/agent runs only — never invoke from CI.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_ID = "fred_macro_daily_2015_2025_v1"
# Provisional: the authoritative spec names the FRED datasets but this session
# does not hold the spec text. DGS3MO (3-month T-bill) + VIXCLS (CBOE VIX close)
# are the two series the program record identifies for the D9-C risk design.
DEFAULT_SERIES = ["DGS3MO", "VIXCLS"]
REQUESTED_START = "2015-01-01"
REQUESTED_END_EXCLUSIVE = "2026-01-01"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
USER_AGENT = "Micap-Research/1.0 (Directive-9 local acquisition)"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_series(series_id: str, *, timeout: int = 30) -> list[tuple[str, str]]:
    """Return [(observation_date, value)] for a FRED series via the keyless CSV endpoint."""
    req = urllib.request.Request(
        FRED_CSV_URL.format(sid=series_id), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed host
        body = resp.read().decode("utf-8", errors="strict")
    rows = list(csv.reader(io.StringIO(body)))
    if len(rows) < 2:
        raise ValueError(f"{series_id}: no data rows returned (got {len(rows)} rows)")
    header, data = rows[0], rows[1:]
    if len(header) < 2:
        raise ValueError(f"{series_id}: unexpected header {header!r}")
    out: list[tuple[str, str]] = []
    for row in data:
        if len(row) < 2:
            continue
        date, value = row[0].strip(), row[1].strip()
        if not date:
            continue
        out.append((date, value))
    if not out:
        raise ValueError(f"{series_id}: header parsed but no usable observations")
    return out


def restrict(rows: list[tuple[str, str]], start: str, end_exclusive: str) -> list[tuple[str, str]]:
    return [(d, v) for d, v in rows if start <= d < end_exclusive]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_dataset_hash(file_hashes: dict[str, str]) -> str:
    """Deterministic hash over sorted path->sha256 pairs (not raw byte concat)."""
    payload = "\n".join(f"{k}:{v}" for k, v in sorted(file_hashes.items())) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_series(path: Path, series_id: str, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["observation_date", series_id])
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-id", default=DATASET_ID)
    p.add_argument("--series", nargs="+", default=DEFAULT_SERIES)
    p.add_argument("--start", default=REQUESTED_START)
    p.add_argument("--end", default=REQUESTED_END_EXCLUSIVE, help="Exclusive end date")
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args(argv)

    out_dir = args.out_dir or (_repo_root() / "data" / "snapshots" / args.dataset_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    retrieval_ts = _utc_now()
    per_series: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}

    print(f"Acquiring {args.dataset_id} (keyless fredgraph.csv)")
    print(f"Requested [{args.start}, {args.end}) series={args.series}")
    for sid in args.series:
        rows = restrict(fetch_series(sid), args.start, args.end)
        if not rows:
            print(f"ERROR: {sid} empty after date filter", file=sys.stderr)
            return 2
        path = out_dir / f"{sid}.csv"
        write_series(path, sid, rows)
        file_hashes[f"{sid}.csv"] = sha256_file(path)
        missing = sum(1 for _, v in rows if v in ("", ".", "NaN"))
        per_series[sid] = {
            "row_count": len(rows),
            "actual_start": rows[0][0],
            "actual_end": rows[-1][0],
            "missing_values": missing,
        }
        print(
            f"  {sid}: rows={len(rows)} actual={rows[0][0]}..{rows[-1][0]} "
            f"missing={missing} -> {path}"
        )

    manifest = {
        "dataset_id": args.dataset_id,
        "source": "fred",
        "source_endpoint": FRED_CSV_URL,
        "auth": "none (keyless CSV endpoint)",
        "series": list(args.series),
        "requested_start": args.start,
        "requested_end_exclusive": args.end,
        "per_series": per_series,
        "retrieval_timestamp_utc": retrieval_ts,
        "status": "DATA FROZEN",
        "sha256": {**file_hashes, "dataset_canonical": canonical_dataset_hash(file_hashes)},
        "notes": (
            "Keyless FRED acquisition. Payload committed under data/snapshots/ so the "
            "snapshot stays recoverable. Series list is provisional pending the "
            "authoritative D9-C spec."
        ),
    }
    (out_dir / f"{args.dataset_id}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_dir / (args.dataset_id + '.json')}")
    print(f"dataset_canonical sha256={manifest['sha256']['dataset_canonical']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
