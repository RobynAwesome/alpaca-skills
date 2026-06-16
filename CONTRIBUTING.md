# Contributing

Thank you for contributing to Alpaca Skills. This repository is open to improvements, new skills, and documentation updates.

## Types of contributions

- **New skills** — workflow packages for Trading API or Broker API tasks
- **Improvements** — clearer instructions, better guardrails, broader CLI coverage
- **Documentation** — README, guides, cookbooks

## Before you open a PR

1. Read [AGENTS.md](AGENTS.md) for layout and frontmatter conventions.
2. Pick a product folder: `skills/trading-api/` or `skills/broker-api/`.
3. Choose a prefixed `name` (e.g. `alpaca-trading-my-skill`) unique within that folder.
4. Copy `templates/skill/` as your starting point.

## Skill requirements

Every skill must include:

- `SKILL.md` with `name` and `description` frontmatter
- `reference.md` companion for schemas, formulas, or CLI detail
- Prerequisites and authentication guidance (no hardcoded secrets)
- Disclosure language for trading-related outputs
- A clear workflow the agent can follow step by step

## Review criteria

Maintainers check for:

- Unique `name` within the product folder
- Disclosure and compliance language where applicable
- Accurate CLI or API references (prefer `alpaca <cmd> --help` and `--schema` over stale examples)
- No committed secrets or credentials

## Pull request process

1. Fork the repository and create a feature branch.
2. Make your changes and self-review against [AGENTS.md](AGENTS.md).
3. Open a PR with a short summary and test plan.
4. A maintainer will review and merge or request changes.

Questions? Open a discussion or issue on GitHub.
