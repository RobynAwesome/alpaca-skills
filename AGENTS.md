# Agent Guidelines

Conventions for authoring and maintaining skills in this repository.

## Repository layout

| Path | Purpose |
| --- | --- |
| `skills/trading-api/` | Trading API agent skills |
| `skills/broker-api/` | Broker API agent skills |
| `templates/skill/` | Contributor scaffold (`SKILL.md` + `reference.md`) |
| `cookbooks/` | End-to-end examples (future) |
| `guides/` | Setup and usage guides (future) |

## Skill structure

| Topic | Rule |
| --- | --- |
| Layout | Skills live under `skills/<product>/<skill-name>/` |
| Frontmatter | Required fields: `name`, `description` only |
| Namespacing | Use product folder (`trading-api/`, `broker-api/`) and a prefixed `name` (e.g. `alpaca-trading-backtest`) |
| File pairing | Every skill has `SKILL.md` (workflow) + `reference.md` (schemas, formulas, CLI detail) |
| Cross-refs | Use relative paths (`reference.md`), not absolute install paths |
| Secrets | Never commit API keys; prefer env vars (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) |
| Disclosures | Trading skills must include disclosure language in outputs |

## Adding a skill

1. Copy `templates/skill/` into the appropriate product folder.
2. Choose a unique prefixed `name` within that product folder.
3. Write workflow and guardrails in `SKILL.md`; put formulas, schemas, and CLI reference in `reference.md`.
4. Open a pull request. A maintainer will review before merge.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full process.
