---
name: alpaca-trading-hackathon-agent
description: >
  Run and demonstrate the repository's narrow, paper-only autonomous Alpaca
  options agent for the Alpaca AI Trading Agents Hackathon. Use when preparing
  a reproducible demo, validating paper-account safety, or explaining the
  strategy and risk gates.
---

# Alpaca Hackathon Agent

Use the runnable example at [../../../examples/paper-options-agent/](../../../examples/paper-options-agent/)
when the user needs a concrete autonomous Alpaca trading-agent demo. This skill
is intentionally paper-only and long-options-only.

The AI host is the orchestration layer: it explains the signal, reviews the
preview, and chooses when to invoke the explicit paper submission command. The
Python runner is the deterministic execution and risk boundary, so generated
language cannot bypass its paper-only or idempotency gates.

## Required workflow

1. Read the example README and inspect `config.example.json`.
2. Confirm the user has a dedicated Alpaca paper account with the hackathon's
   required $100,000 starting balance and options trading level 2 or higher.
3. Require credentials from `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` (the
   example also accepts `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`). Never ask the
   user to paste credentials into chat.
4. Run the dry-run command first:

   ```text
   python examples/paper-options-agent/agent.py --config examples/paper-options-agent/config.example.json --json
   ```

5. Explain the signal, selected contract, expiration, spread, premium budget,
   and risk gates from the returned preview.
6. Submit only when the user explicitly requests a paper submission and the
   preview has been reviewed:

   ```text
   python examples/paper-options-agent/agent.py --config examples/paper-options-agent/config.example.json --submit --json
   ```

7. Record the paper order ID, status, and dashboard evidence without exposing
   secrets or an unredacted account identifier.

## Hard safety requirements

- The example must use the literal `https://paper-api.alpaca.markets` endpoint.
- A live endpoint, live environment, live-trading flag, blocked account, or
  missing account safety field stops execution.
- Options level 2 is required because the example buys calls.
- A fresh bullish 20/50-day SMA crossover is required; no signal means no
  order.
- One existing option position or working option order for the underlying
  blocks additional exposure.
- The order is a day limit order with `buy_to_open`, a deterministic
  `client_order_id`, a 21-45 DTE contract, a maximum 10% bid/ask spread, and
  a premium cap of the lower of $1,000, 2% of equity, and buying power.
- The daily loss gate defaults to 2%, and the minimum equity gate defaults to
  $100,000 for the hackathon demo.
- `--submit` is never implied by a dry run. Do not bypass the gate or switch to
  live trading.

## Required disclosure

> This is an educational paper-trading example, not investment advice. Paper
> results are simulated and may differ from live trading. Options involve
> substantial risk and can expire worthless. Review
> [Alpaca disclosures](https://alpaca.markets/disclosures) before use.
