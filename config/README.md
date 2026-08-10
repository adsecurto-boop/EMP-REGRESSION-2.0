# Configuration

Governed by [`docs/ADS/configuration_standard.md`](../docs/ADS/configuration_standard.md). All configuration is read through `framework/shared/config.py`; no other component reads these files directly.

## Files

| File | Purpose |
|---|---|
| `framework.json` | Base configuration — defaults for every environment |
| `environments/<name>.json` | Per-environment overlay, merged over the base |

JSON is used throughout because it needs no third-party dependency. YAML (`.yaml`/`.yml`) is also supported when PyYAML is installed; the loader prefers `.json` when both exist.

## Precedence

Lowest to highest:

1. `framework.json`
2. `environments/<environment>.json`
3. Environment variables prefixed `EMPAF_`

Nested keys use a double underscore: `EMPAF_LOGGING__LEVEL=DEBUG` overrides `logging.level`. Values are coerced to JSON-native types, so `EMPAF_EVIDENCE__STRICT=false` sets a boolean.

Two variables are reserved and are not treated as configuration overrides:

| Variable | Effect |
|---|---|
| `EMPAF_ENVIRONMENT` | Selects the environment overlay (default `local`) |
| `EMPAF_CONFIG_DIR` | Overrides this directory's location |

Strings support `${VAR}` and `${VAR:-default}` substitution against process environment variables.

## `evidence.sources` — the Evidence Catalog mirror

This block is the machine-readable mirror of [`docs/Evidence_Catalog.md`](../docs/Evidence_Catalog.md). The document stays authoritative for humans; this block is what the running framework validates against, so that registering a source is a configuration change rather than a code change.

**These must be kept in step.** Adding a row to the catalog document without adding it here means the framework will reject evidence from that source; the reverse means the framework admits evidence no document explains. Either direction is drift — see the risk recorded in [`docs/IMPLEMENTATION_REVIEW.md`](../docs/IMPLEMENTATION_REVIEW.md).

Each entry carries:

| Key | Meaning |
|---|---|
| `id` | Catalog identifier, `EV-NNN` |
| `name` | Source name as registered in the catalog |
| `layer` | Evidence layer, `1`–`4` |
| `reliability` | `high` / `medium` / `low`, per the catalog's §2.1 rubric |
| `collector` | Component responsible for collecting it |
| `implemented` | Whether that collector exists yet |

Every source is currently `"implemented": false`: Phase 1 delivers the foundation, and no collector has been built. `evidence.strict` remains `true` so that when collectors do arrive they cannot cite unregistered sources.

## Adding a key

Per the Configuration Standard's checklist: add it here with a default, document it, and add validation to `framework/validators/configuration.py` when that validator is built. Structural validation the framework cannot start without lives in `ConfigurationManager._validate`.
