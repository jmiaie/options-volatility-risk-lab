# Data layout (Directive #9)

| Path | Tracked? | Purpose |
|---|---|---|
| `data/raw/` | **No** (gitignored) | Frozen Yahoo Finance underlying snapshots. Never commit. |
| `data/manifests/` | **Yes** | Provenance manifests + SHA-256 after freeze. |

**Acquisition:** local/agent only via `scripts/acquire_yf_options_risk_underlyings_daily.py`. Never from CI.

**Scope:** underlyings (SPY/QQQ/IWM) only. No paid options tapes.
