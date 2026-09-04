# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `main` | Yes |

This repository does not publish semver releases yet. Security fixes land on `main`.

## Reporting a vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

Preferred channel: [GitHub Security Advisories](https://github.com/RobynAwesome/alpaca-skills/security/advisories/new) (private).

Alternate: email **security@alpaca.markets** with:

- Description of the issue
- Steps to reproduce
- Impact assessment (if known)

## Response targets

- Initial acknowledgment: within ~48 hours
- Status update: within ~7 days
- Fix timeline: varies by severity

## Scope

In scope:

- Credential handling in skills
- Malicious skill content
- Secrets committed in pull requests

Out of scope:

- Trading losses or P&L outcomes from backtest or paper-trading output

## API keys and credentials

Never commit Alpaca API keys, secret keys, or tokens in issues or pull requests. Use environment variables as described in [AGENTS.md](AGENTS.md).
