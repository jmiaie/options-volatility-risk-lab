# Data layout (Directive #9)

| Path | Tracked? | Purpose |
|---|---|---|
| `data/raw/` | **No** (must be gitignored) | Frozen FRED/Yahoo snapshots. Never commit. |
| `data/manifests/` | **Yes** | Provenance manifests + checksums after freeze. |

Scaffold only — acquisition not started.
