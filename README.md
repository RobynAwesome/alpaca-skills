# Alpaca Skills

Open agent skills for Alpaca's Trading API and Broker API. Each skill is a `SKILL.md` file with step-by-step instructions your AI coding assistant follows when you ask it to complete a task — such as running a historical backtest or fetching market data through the Alpaca CLI.

Skills provide shared instructions, guardrails, and reporting standards so agents produce more consistent results across runs.

## Disclaimer

Skills and their outputs are for research and educational purposes only. They are not investment advice, a recommendation, an offer, or a solicitation to buy or sell securities or other financial products. All investments involve risk and may lose value. Review [Alpaca's disclosures](https://alpaca.markets/disclosures) before trading.

## Prerequisites

- **[Alpaca CLI](https://github.com/alpacahq/cli)** — install via Homebrew or Go:

  ```bash
  brew install alpacahq/tap/cli
  # or
  go install github.com/alpacahq/cli/cmd/alpaca@latest
  ```

- **Alpaca API credentials** — paper or live keys for the CLI. Run `alpaca profile login` or set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.

## Install

Point your agent at a skill directory, or copy it into your agent's skills folder.

| Agent | Typical path |
| --- | --- |
| **Cursor** | Copy or symlink `skills/trading-api/backtest/` into `.cursor/skills/` (project) or your user skills directory |
| **Claude Code** | Copy into `~/.claude/skills/` |
| **Other** | Reference the `SKILL.md` path directly in your agent prompt |

Example (Cursor project skill):

```bash
mkdir -p .cursor/skills
cp -r path/to/alpaca-skills/skills/trading-api/backtest .cursor/skills/alpaca-trading-backtest
```

## Available skills

| Name | Path | Title |
| --- | --- | --- |
| `alpaca-trading-backtest` | [skills/trading-api/backtest/](skills/trading-api/backtest/) | Trading API Backtesting |

Product namespacing uses the folder path (`skills/trading-api/`, `skills/broker-api/`) and the skill `name` field in frontmatter.

## Related resources

- [Alpaca CLI](https://github.com/alpacahq/cli)
- [Trading API documentation](https://docs.alpaca.markets/)
- [Alpaca disclosures](https://alpaca.markets/disclosures)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Agent conventions for skill authors are in [AGENTS.md](AGENTS.md).
