# Paper Options Agent

This is the runnable demo path for the Alpaca AI Trading Agents Hackathon. It
implements a deliberately small autonomous strategy:

1. Fetch completed daily bars for `SPY`.
2. Detect a fresh bullish 20/50-day SMA crossover.
3. Confirm a dedicated paper account, options level 2, buying power, daily loss
   limit, and absence of existing `SPY` options exposure.
4. Fetch delayed/derived indicative option snapshots and select one liquid call
   21-45 days from expiration.
5. Cap premium at the lower of $1,000, 2% of equity, and buying power.
6. Submit a day limit order with `buy_to_open` and a deterministic client order
   ID, only when `--submit` is explicitly passed.

The trading endpoint is a literal `https://paper-api.alpaca.markets` in
`agent.py`. The example has no live-trading switch. A live endpoint or live
environment variable causes an immediate block.

## AI-agent integration

This repository is an agent-skill project rather than a hosted LLM service.
Load [`skills/trading-api/hackathon-agent/SKILL.md`](../../skills/trading-api/hackathon-agent/SKILL.md)
into a compatible AI host. The host explains the signal, reviews the JSON
preview with the operator, and decides whether to invoke the runner's explicit
paper submission path. The Python runner remains the deterministic execution
and risk boundary; generated language cannot bypass its paper-only or
idempotency gates.

## Setup

Use Python 3.10 or later and a dedicated Alpaca paper account. For the
hackathon demo, reset or create the account with the required $100,000 starting
balance and enable options trading at level 2 or higher. Do not use live
credentials.

PowerShell:

```powershell
$env:APCA_API_KEY_ID = "your-paper-key"
$env:APCA_API_SECRET_KEY = "your-paper-secret"
```

The aliases `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are also accepted. Keep
credentials in the environment; never put them in this repository.

## Run

From this directory:

```text
python agent.py --config config.example.json --json
```

The default is a dry run. Review the JSON preview, then explicitly submit one
paper order:

```text
python agent.py --config config.example.json --submit --json
```

For unattended paper polling, run the same command with an interval:

```text
python agent.py --config config.example.json --submit --loop-seconds 300 --json
```

The deterministic client order ID and exposure checks prevent a second order
for the same strategy day. A scheduler such as Windows Task Scheduler or cron
can invoke the one-shot command instead of keeping a process alive.

Run the local tests from the repository root:

```text
python examples/paper-options-agent/test_agent.py
```

## Demo narrative

Show the dry-run JSON first, then show the paper account and options approval
in the Alpaca dashboard, and finally run the explicit `--submit` command. The
demo should call out the environment assertion, signal calculation, contract
selection, indicative data feed, premium budget, spread gate, expiration
window, and idempotency key. Capture the order ID and paper fill from the
dashboard; do not expose API keys or unredacted account identifiers.

## Scope and limitations

This example is intentionally a narrow hackathon demonstration. It buys long
calls only; it does not sell options, exercise contracts, manage a portfolio,
or claim profitability. It relies on Alpaca's current REST response fields and
uses the indicative options feed rather than subscribed OPRA data, so quotes
may be delayed or derived. It should be checked against current API schemas
before reuse. It is not a
replacement for the broader paper-trading skill, which covers equities,
options, crypto, monitoring, and additional order lifecycle behavior.

**Disclosure:** This is an educational paper-trading example, not investment
advice. Paper results are simulated and may differ from live trading. Options
involve substantial risk and can expire worthless. Review
[Alpaca disclosures](https://alpaca.markets/disclosures) and the
[OCC Options Disclosure Document](https://www.theocc.com/company-information/documents-and-archives/options-disclosure-document?ref=alpaca.markets).
