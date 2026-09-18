# PROVENANCE — fred_macro_daily_2015_2025_v1

**Why this file exists.** The D9-C remediation requires FRED macro series alongside the equity
underlyings, and the agent session that ran the exploratory study cannot fetch them: its egress
proxy returns an organization-policy 403 for `fred.stlouisfed.org` (and Yahoo/SEC), recorded in the
D9 tracker as a deliberate policy denial — not a transient error. Acquisition therefore runs on a
node with unrestricted egress (Hai) and ships a frozen, committed snapshot.

**How it was made.** 2026-09-17, node Hai (Tailscale 100.111.189.7), via the new keyless script
`scripts/acquire_fred_macro_daily.py`. No API key: the public endpoint
`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` is unauthenticated.

| series | meaning | rows | actual range | missing values |
|---|---|---:|---|---:|
| `DGS3MO` | 3-month Treasury bill, secondary market, daily | 2870 | 2015-01-01..2025-12-31 | 120 |
| `VIXCLS` | CBOE volatility index, close | 2870 | 2015-01-01..2025-12-31 | 77 |

Missing values are FRED's own non-observation markers (`.`): weekends and market holidays are
carried as rows with a `.` value rather than dropped, so the absence is visible in the artifact.

**Reproduce.**
`python scripts/acquire_fred_macro_daily.py --dataset-id fred_macro_daily_2015_2025_v1`

**Status: PROVISIONAL — pending the authoritative D9-C spec.** The program record identifies
"D9-C — material fail (missing FRED datasets / design)" and the two series above, but the
authoritative spec text (exact series list, risk-design changes, canonical dataset ID) is not held
by this session. Until the spec is applied and its own acquire/freeze/hash cycle runs:

- this dataset ID and series list may change;
- nothing here may be cited as satisfying the D9-C spec;
- no result computed from it may be presented as the D9-C historical result.

**Lesson applied.** The D9-A v1 payload became unrecoverable because raw CSVs were gitignored
repo-wide and only a manifest was committed. This snapshot commits the payload itself.
