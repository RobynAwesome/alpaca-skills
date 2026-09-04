import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from agent import (  # noqa: E402
    AgentBlocked,
    AlpacaClient,
    OptionSelection,
    StrategyConfig,
    build_order,
    evaluate_signal,
    run_once,
    select_option,
    validate_account,
    validate_paper_environment,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RecordingOpener:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: object, timeout: int) -> FakeResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("The test client made more requests than expected.")
        return FakeResponse(self.responses.pop(0))


class MockAgentClient:
    def __init__(self) -> None:
        self.submissions = []
        self.existing_order_ids = set()
        self.expiration = datetime.now(timezone.utc).date() + timedelta(days=30)
        self.option_symbol = f"SPY{self.expiration:%y%m%d}C00505000"

    def account(self) -> dict[str, str | bool]:
        return {
            "id": "12345678-1234-1234-1234-123456789012",
            "status": "ACTIVE",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
            "equity": "100000",
            "last_equity": "100000",
            "buying_power": "100000",
            "options_trading_level": "2",
        }

    def clock(self) -> dict[str, bool]:
        return {"is_open": True}

    def daily_bars(self, symbol: str, limit: int) -> list[dict[str, int]]:
        return [{"c": 1}, {"c": 1}, {"c": 1}, {"c": 2}]

    def positions(self) -> list[dict[str, str]]:
        return []

    def open_orders(self, underlying: str | None = None) -> list[dict[str, str]]:
        return []

    def latest_quote(self, symbol: str) -> dict[str, str]:
        return {"bp": "504", "ap": "506"}

    def option_contracts(
        self, underlying: str, minimum_expiration: date, maximum_expiration: date
    ) -> list[dict[str, str | bool]]:
        return [
            {
                "symbol": self.option_symbol,
                "type": "call",
                "status": "active",
                "tradable": True,
                "expiration_date": self.expiration.isoformat(),
                "strike_price": "505",
                "multiplier": "100",
            }
        ]

    def option_snapshots(self, symbols: list[str]) -> dict[str, dict[str, int | str]]:
        return {
            self.option_symbol: {
                "bid_price": "4.90",
                "ask_price": "5.00",
                "volume": 10,
            }
        }

    def order_by_client_id(self, client_order_id: str) -> dict[str, str] | None:
        if client_order_id in self.existing_order_ids:
            return {"client_order_id": client_order_id}
        return None

    def submit_order(self, payload: dict[str, str]) -> dict[str, str]:
        self.submissions.append(payload)
        self.existing_order_ids.add(payload["client_order_id"])
        return {
            "id": "order-1",
            "client_order_id": payload["client_order_id"],
            "status": "accepted",
            "symbol": payload["symbol"],
            "qty": payload["qty"],
            "limit_price": payload["limit_price"],
        }


class AgentUnitTests(unittest.TestCase):
    def test_signal_requires_a_fresh_bullish_crossover(self) -> None:
        config = StrategyConfig(fast_window=2, slow_window=3, minimum_equity=0)
        signal = evaluate_signal([1, 1, 1, 2], config)
        self.assertTrue(signal.triggered)

    def test_option_selection_rejects_wide_spreads_and_respects_budget(self) -> None:
        config = StrategyConfig(
            fast_window=2,
            slow_window=3,
            max_premium=500,
            max_contracts=2,
            minimum_equity=0,
        )
        contracts = [
            {
                "symbol": "SPY260415C00500000",
                "type": "call",
                "status": "active",
                "tradable": True,
                "expiration_date": "2026-04-15",
                "strike_price": "500",
                "bid_price": "1.00",
                "ask_price": "2.00",
                "volume": 10,
                "multiplier": 100,
                "size": 100,
            },
            {
                "symbol": "SPY260415C00505000",
                "type": "call",
                "status": "active",
                "tradable": True,
                "expiration_date": "2026-04-15",
                "strike_price": "505",
                "bid_price": "4.90",
                "ask_price": "5.00",
                "volume": 10,
                "multiplier": 100,
                "size": 1,
            },
        ]
        selected = select_option(
            contracts,
            underlying_price=505,
            equity=100000,
            buying_power=100000,
            as_of=date(2026, 3, 1),
            config=config,
        )
        self.assertEqual(selected.symbol, "SPY260415C00505000")
        self.assertEqual(selected.quantity, 1)
        self.assertEqual(selected.estimated_premium, 500)

    def test_order_contains_idempotent_options_fields(self) -> None:
        selection = OptionSelection(
            symbol="SPY260415C00505000",
            expiration_date=date(2026, 4, 15),
            dte=45,
            strike=505,
            bid=4.9,
            ask=5.0,
            spread_pct=0.02,
            multiplier=100,
            quantity=1,
            estimated_premium=500,
        )
        order = build_order(selection, "SPY", date(2026, 3, 1))
        self.assertEqual(order["position_intent"], "buy_to_open")
        self.assertEqual(order["time_in_force"], "day")
        self.assertTrue(order["client_order_id"].startswith("hackathon-spy-"))

    def test_account_gate_requires_options_level_two(self) -> None:
        account = {
            "id": "12345678-1234-1234-1234-123456789012",
            "status": "ACTIVE",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
            "equity": "100000",
            "last_equity": "100000",
            "buying_power": "100000",
            "options_trading_level": "1",
        }
        with self.assertRaises(AgentBlocked):
            validate_account(account, StrategyConfig())

    def test_account_gate_requires_positive_prior_equity(self) -> None:
        account = {
            "id": "12345678-1234-1234-1234-123456789012",
            "status": "ACTIVE",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
            "equity": "100000",
            "last_equity": "0",
            "buying_power": "100000",
            "options_trading_level": "2",
        }
        with self.assertRaises(AgentBlocked):
            validate_account(account, StrategyConfig())

    def test_live_endpoint_override_is_blocked(self) -> None:
        with patch.dict(os.environ, {"APCA_API_BASE_URL": "https://api.alpaca.markets"}):
            with self.assertRaises(AgentBlocked):
                validate_paper_environment()

    def test_option_contracts_follow_next_page_token(self) -> None:
        opener = RecordingOpener(
            [
                {
                    "option_contracts": [{"symbol": "SPY260415C00500000"}],
                    "next_page_token": "contracts-page-2",
                },
                {"option_contracts": [{"symbol": "SPY260415C00505000"}]},
            ]
        )
        client = AlpacaClient("key", "secret", opener=opener)

        contracts = client.option_contracts(
            "SPY", date(2026, 3, 1), date(2026, 4, 15)
        )

        self.assertEqual(
            [contract["symbol"] for contract in contracts],
            ["SPY260415C00500000", "SPY260415C00505000"],
        )
        first_query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        second_query = parse_qs(urlsplit(opener.requests[1].full_url).query)
        self.assertEqual(first_query["limit"], ["10000"])
        self.assertEqual(second_query["page_token"], ["contracts-page-2"])

    def test_daily_bars_exclude_current_incomplete_bar(self) -> None:
        opener = RecordingOpener([{"bars": [{"c": "1"}]}])
        client = AlpacaClient("key", "secret", opener=opener)

        self.assertEqual(client.daily_bars("SPY", 51), [{"c": "1"}])
        query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        expected_end = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        self.assertEqual(query["end"], [expected_end])

    def test_option_snapshots_batch_at_one_hundred_and_page(self) -> None:
        symbols = [f"OPT{i:03d}" for i in range(100)] + ["OPT000", "OPT100"]
        opener = RecordingOpener(
            [
                {
                    "snapshots": {
                        "OPT000": {"latest_quote": {"bp": "1", "ap": "2"}}
                    },
                    "next_page_token": "snapshots-page-2",
                },
                {
                    "snapshots": {
                        "OPT001": {"latest_quote": {"bp": "2", "ap": "3"}}
                    }
                },
                {
                    "snapshots": {
                        "OPT100": {"latest_quote": {"bp": "3", "ap": "4"}}
                    }
                },
            ]
        )
        client = AlpacaClient("key", "secret", opener=opener)

        snapshots = client.option_snapshots(symbols)

        self.assertEqual(set(snapshots), {"OPT000", "OPT001", "OPT100"})
        first_query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        second_query = parse_qs(urlsplit(opener.requests[1].full_url).query)
        third_query = parse_qs(urlsplit(opener.requests[2].full_url).query)
        self.assertEqual(len(first_query["symbols"][0].split(",")), 100)
        self.assertEqual(len(third_query["symbols"][0].split(",")), 1)
        self.assertEqual(first_query["limit"], ["1000"])
        self.assertEqual(second_query["page_token"], ["snapshots-page-2"])
        self.assertNotIn("page_token", third_query)

    def test_open_orders_use_maximum_documented_page_size(self) -> None:
        opener = RecordingOpener([[]])
        client = AlpacaClient("key", "secret", opener=opener)

        self.assertEqual(client.open_orders("SPY"), [])
        query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        self.assertEqual(query["limit"], ["500"])

    def test_run_once_supports_dry_run_and_blocks_duplicate_submission(self) -> None:
        config = StrategyConfig(
            fast_window=2,
            slow_window=3,
            max_premium=500,
            max_contracts=1,
            minimum_equity=0,
        )
        client = MockAgentClient()
        paper_env = {
            "APCA_API_BASE_URL": "",
            "ALPACA_API_BASE_URL": "",
            "ALPACA_TRADING_BASE_URL": "",
            "ALPACA_ENV": "",
            "APCA_ENV": "",
            "ALPACA_TRADING_ENV": "",
            "ALPACA_LIVE_TRADING": "",
            "APCA_LIVE_TRADING": "",
        }

        with patch.dict(os.environ, paper_env):
            preview = run_once(client, config, submit=False)
            submitted = run_once(client, config, submit=True)
            with self.assertRaises(AgentBlocked):
                run_once(client, config, submit=True)

        self.assertEqual(preview["action"], "preview")
        self.assertEqual(submitted["action"], "submit")
        self.assertEqual(len(client.submissions), 1)


if __name__ == "__main__":
    unittest.main()
