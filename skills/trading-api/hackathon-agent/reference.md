# Hackathon Agent Reference

## Runtime files

| File | Purpose |
|---|---|
| `examples/paper-options-agent/agent.py` | Standard-library REST client, strategy, gates, and CLI |
| `examples/paper-options-agent/config.example.json` | Non-secret strategy defaults |
| `examples/paper-options-agent/test_agent.py` | Unit coverage for signal, selection, sizing, and safety gates |

## API calls

The example uses:

| API | Endpoint |
|---|---|
| Account | `GET https://paper-api.alpaca.markets/v2/account` |
| Clock | `GET https://paper-api.alpaca.markets/v2/clock` |
| Positions | `GET https://paper-api.alpaca.markets/v2/positions` |
| Open orders | `GET https://paper-api.alpaca.markets/v2/orders` |
| Idempotency lookup | `GET https://paper-api.alpaca.markets/v2/orders:by_client_order_id` |
| Submit | `POST https://paper-api.alpaca.markets/v2/orders` |
| Daily bars | `GET https://data.alpaca.markets/v2/stocks/{symbol}/bars` |
| Latest quote | `GET https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest` |
| Option chain | `GET https://paper-api.alpaca.markets/v2/options/contracts` |
| Option snapshots | `GET https://data.alpaca.markets/v1beta1/options/snapshots` |

Contract pages request the documented maximum `limit=10000` and follow
`next_page_token` with `page_token` until the token is absent. Snapshot requests
are batched to no more than 100 symbols, request `limit=1000`, and follow the
same token pattern. Open-order checks request `limit=500`; because the endpoint
does not expose a documented pagination token, the runtime refuses to trade if
exactly 500 open orders are returned rather than risking incomplete
duplicate-order coverage.
Snapshots use `feed=indicative`, which is delayed/derived options data; do not
describe it as a live OPRA quote feed.

The API key and secret are sent only as request headers. They are never
printed, serialized, or included in result JSON.

## Strategy and risk formulas

```text
SMA(n) = sum(last n completed closes) / n
bullish_signal = previous_fast <= previous_slow AND fast > slow
spread_pct = (ask - bid) / ask
estimated_premium = ask × contract_multiplier × quantity
max_notional = min(max_premium, equity × max_position_pct, buying_power)
```

The runtime reads the contract `multiplier` field and rejects missing or
non-positive values. Do not substitute the `size` field: `size` describes the
underlying shares delivered on exercise and can differ for non-standard
contracts. The default budget is:

```text
max_premium = $1,000
max_position_pct = 2%
max_contracts = 1
max_spread_pct = 10%
minimum_dte = 21
maximum_dte = 45
max_daily_loss_pct = 2%
minimum_equity = $100,000
```

## Order contract

```json
{
  "side": "buy",
  "type": "limit",
  "time_in_force": "day",
  "position_intent": "buy_to_open",
  "qty": "1",
  "limit_price": "0.00",
  "client_order_id": "hackathon-spy-YYYYMMDD-contracthash"
}
```

The limit price is the current option ask, rounded to two decimals. The client
order ID is deterministic for the underlying, UTC strategy date, and contract,
so a timeout or repeated scheduler invocation can check for the original
order before retrying.

## Current Alpaca sources

- [Trading API](https://docs.alpaca.markets/us/docs/trading-api)
- [Options trading](https://docs.alpaca.markets/us/docs/options-trading)
- [Working with orders](https://docs.alpaca.markets/us/docs/working-with-orders)
- [Working with account](https://docs.alpaca.markets/us/docs/working-with-account)
- [Working with assets](https://docs.alpaca.markets/us/docs/working-with-assets)
- [Paper trading](https://docs.alpaca.markets/us/docs/paper-trading)
