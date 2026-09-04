#!/usr/bin/env python3
"""Paper-only autonomous options agent for the Alpaca hackathon demo.

The example intentionally uses only the Python standard library so it can be
run from a clean checkout. It is a long-call strategy example, not investment
advice or a production trading system.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


PAPER_TRADING_URL = "https://paper-api.alpaca.markets"
MARKET_DATA_URL = "https://data.alpaca.markets"
DISCLOSURE = (
    "This is an educational paper-trading example, not investment advice. "
    "Paper results are simulated and may differ from live trading. Options "
    "involve substantial risk and can expire worthless. Review "
    "https://alpaca.markets/disclosures before use."
)


class AgentError(RuntimeError):
    """A user-actionable configuration, safety, or API error."""


class AgentBlocked(AgentError):
    """A trade was intentionally blocked by a safety gate."""


class ApiError(AgentError):
    """An Alpaca API request returned a non-success response."""

    def __init__(self, status: int, path: str, message: str) -> None:
        self.status = status
        self.path = path
        self.message = message
        super().__init__(f"Alpaca API error {status} for {path}: {message}")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise AgentError(f"Alpaca response did not include numeric {field}.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentError(f"Alpaca response included invalid numeric {field}.") from exc
    if not math.isfinite(result):
        raise AgentError(f"Alpaca response included non-finite numeric {field}.")
    return result


def _integer(value: Any, field: str) -> int:
    number = _number(value, field)
    if not number.is_integer():
        raise AgentError(f"Alpaca response included non-integer {field}.")
    return int(number)


def _flag(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise AgentError(f"Alpaca response did not include a boolean {field}.")


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise AgentError(f"Alpaca response did not include {field}.")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise AgentError(f"Alpaca response included invalid {field}.") from exc


def _redact_account_id(value: Any) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "redacted"
    return f"{text[:4]}...{text[-4:]}"


def _sma(values: list[float], window: int) -> float:
    if window <= 0 or len(values) < window:
        raise AgentError(f"At least {window} completed prices are required.")
    return sum(values[-window:]) / window


def _extract_list(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in keys:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None:
            raise AgentError(f"Alpaca response did not include one of: {', '.join(keys)}.")
    else:
        raise AgentError("Alpaca response was not a JSON object or list.")

    if not all(isinstance(item, dict) for item in items):
        raise AgentError("Alpaca response included an invalid list item.")
    return items


def _next_page_token(payload: Any, path: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    token = payload.get("next_page_token")
    if token is None:
        return None
    if not isinstance(token, str) or not token:
        raise AgentError(f"Alpaca response included an invalid next_page_token for {path}.")
    return token


def _occ_root(symbol: str) -> str | None:
    match = re.match(r"^(.+?)(\d{6}[CP]\d{8})$", symbol.upper())
    return match.group(1) if match else None


def _is_option_for(symbol: Any, underlying: str) -> bool:
    return _occ_root(str(symbol or "")) == underlying.upper()


def validate_paper_environment() -> None:
    """Reject live overrides even though the client pins the paper URL."""

    for variable in (
        "APCA_API_BASE_URL",
        "ALPACA_API_BASE_URL",
        "ALPACA_TRADING_BASE_URL",
    ):
        value = os.getenv(variable)
        if value and value.rstrip("/") != PAPER_TRADING_URL:
            raise AgentBlocked(
                f"{variable} is set to a non-paper endpoint; refusing to trade."
            )

    for variable in ("ALPACA_ENV", "APCA_ENV", "ALPACA_TRADING_ENV"):
        value = os.getenv(variable)
        if value and value.lower() in {"live", "production"}:
            raise AgentBlocked(f"{variable} requests live trading; refusing to trade.")

    for variable in ("ALPACA_LIVE_TRADING", "APCA_LIVE_TRADING"):
        value = os.getenv(variable)
        if value and value.lower() in {"1", "true", "yes", "on"}:
            raise AgentBlocked(f"{variable} requests live trading; refusing to trade.")


def credentials_from_environment() -> tuple[str, str]:
    validate_paper_environment()
    key = next(
        (os.getenv(name) for name in ("APCA_API_KEY_ID", "ALPACA_API_KEY") if os.getenv(name)),
        None,
    )
    secret = next(
        (
            os.getenv(name)
            for name in ("APCA_API_SECRET_KEY", "ALPACA_SECRET_KEY")
            if os.getenv(name)
        ),
        None,
    )
    if not key or not secret:
        raise AgentError(
            "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY "
            "(ALPACA_API_KEY and ALPACA_SECRET_KEY are also accepted)."
        )
    return key, secret


class AlpacaClient:
    """Small REST client whose trading endpoint is permanently paper-only."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._opener = opener

    def _request(
        self,
        method: str,
        service: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        base_url = PAPER_TRADING_URL if service == "trading" else MARKET_DATA_URL
        query = urlencode(
            [(key, value) for key, value in (params or {}).items() if value is not None]
        )
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{query}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=body,
            headers={
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._secret_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            try:
                decoded = json.loads(raw.decode("utf-8")) if raw else {}
            except json.JSONDecodeError:
                decoded = {}
            message = decoded.get("message") if isinstance(decoded, dict) else None
            raise ApiError(exc.code, path, str(message or "request rejected")) from exc
        except (URLError, TimeoutError) as exc:
            raise AgentError(f"Alpaca API request failed for {path}: {exc}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentError(f"Alpaca returned invalid JSON for {path}.") from exc

    def account(self) -> dict[str, Any]:
        payload = self._request("GET", "trading", "/v2/account")
        if not isinstance(payload, dict):
            raise AgentError("Alpaca account response was not an object.")
        return payload

    def clock(self) -> dict[str, Any]:
        payload = self._request("GET", "trading", "/v2/clock")
        if not isinstance(payload, dict):
            raise AgentError("Alpaca clock response was not an object.")
        return payload

    def positions(self) -> list[dict[str, Any]]:
        return _extract_list(self._request("GET", "trading", "/v2/positions"))

    def open_orders(self, underlying: str | None = None) -> list[dict[str, Any]]:
        orders = _extract_list(
            self._request(
                "GET",
                "trading",
                "/v2/orders",
                params={"status": "open", "limit": 500, "nested": "false"},
            )
        )
        if len(orders) >= 500:
            raise AgentBlocked(
                "Alpaca returned the maximum 500 open orders; refusing to trade "
                "without complete duplicate-order coverage."
            )
        if underlying:
            return [
                order
                for order in orders
                if _is_option_for(order.get("symbol"), underlying)
            ]
        return orders

    def order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        try:
            payload = self._request(
                "GET",
                "trading",
                "/v2/orders:by_client_order_id",
                params={"client_order_id": client_order_id},
            )
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(payload, dict):
            raise AgentError("Alpaca order response was not an object.")
        return payload

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", "trading", "/v2/orders", payload=payload)
        if not isinstance(response, dict):
            raise AgentError("Alpaca order response was not an object.")
        return response

    def daily_bars(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "data",
            f"/v2/stocks/{quote(symbol, safe='')}/bars",
            params={
                "timeframe": "1Day",
                "limit": limit,
                "feed": "iex",
                "sort": "asc",
                # Exclude today's potentially incomplete bar.
                "end": (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
            },
        )
        return _extract_list(payload, "bars")

    def latest_quote(self, symbol: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            "data",
            f"/v2/stocks/{quote(symbol, safe='')}/quotes/latest",
            params={"feed": "iex"},
        )
        if isinstance(payload, dict) and isinstance(payload.get("quote"), dict):
            return payload["quote"]
        if isinstance(payload, dict):
            return payload
        raise AgentError("Alpaca quote response was not an object.")

    def option_contracts(
        self, underlying: str, minimum_expiration: date, maximum_expiration: date
    ) -> list[dict[str, Any]]:
        contracts: list[dict[str, Any]] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            payload = self._request(
                "GET",
                "trading",
                "/v2/options/contracts",
                params={
                    "underlying_symbols": underlying,
                    "status": "active",
                    "expiration_date_gte": minimum_expiration.isoformat(),
                    "expiration_date_lte": maximum_expiration.isoformat(),
                    "type": "call",
                    "limit": 10000,
                    "page_token": page_token,
                },
            )
            contracts.extend(_extract_list(payload, "option_contracts", "contracts"))
            next_token = _next_page_token(payload, "/v2/options/contracts")
            if next_token is None:
                return contracts
            if next_token in seen_tokens:
                raise AgentError(
                    "Alpaca returned a repeated option-contract pagination token."
                )
            seen_tokens.add(next_token)
            page_token = next_token

    def option_snapshots(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        snapshots: dict[str, dict[str, Any]] = {}
        unique_symbols = list(dict.fromkeys(symbols))
        for offset in range(0, len(unique_symbols), 100):
            batch = unique_symbols[offset : offset + 100]
            page_token: str | None = None
            seen_tokens: set[str] = set()
            while True:
                payload = self._request(
                    "GET",
                    "data",
                    "/v1beta1/options/snapshots",
                    params={
                        "symbols": ",".join(batch),
                        "feed": "indicative",
                        "limit": 1000,
                        "page_token": page_token,
                    },
                )
                raw = payload.get("snapshots") if isinstance(payload, dict) else None
                if raw is None:
                    raw = payload
                if isinstance(raw, dict):
                    entries = raw.items()
                elif isinstance(raw, list):
                    entries = (
                        (str(item.get("symbol") or ""), item)
                        for item in raw
                        if isinstance(item, dict)
                    )
                else:
                    raise AgentError(
                        "Alpaca options snapshot response was not an object or list."
                    )

                for symbol, snapshot in entries:
                    if not symbol or not isinstance(snapshot, dict):
                        continue
                    quote = (
                        snapshot.get("latest_quote")
                        or snapshot.get("latestQuote")
                        or {}
                    )
                    if not isinstance(quote, dict):
                        continue
                    normalized: dict[str, Any] = {}
                    if quote.get("bp") is not None:
                        normalized["bid_price"] = quote["bp"]
                    if quote.get("ap") is not None:
                        normalized["ask_price"] = quote["ap"]
                    daily_bar = (
                        snapshot.get("daily_bar")
                        or snapshot.get("dailyBar")
                        or {}
                    )
                    if isinstance(daily_bar, dict) and daily_bar.get("v") is not None:
                        normalized["volume"] = daily_bar["v"]
                    snapshots[symbol] = normalized

                next_token = _next_page_token(payload, "/v1beta1/options/snapshots")
                if next_token is None:
                    break
                if next_token in seen_tokens:
                    raise AgentError(
                        "Alpaca returned a repeated option-snapshot pagination token."
                    )
                seen_tokens.add(next_token)
                page_token = next_token
        return snapshots


@dataclass(frozen=True)
class StrategyConfig:
    underlying: str = "SPY"
    fast_window: int = 20
    slow_window: int = 50
    minimum_dte: int = 21
    maximum_dte: int = 45
    max_position_pct: float = 0.02
    max_premium: float = 1000.0
    max_contracts: int = 1
    max_spread_pct: float = 0.10
    max_daily_loss_pct: float = 0.02
    minimum_equity: float = 100000.0


@dataclass(frozen=True)
class Signal:
    triggered: bool
    close: float
    previous_fast: float
    previous_slow: float
    fast: float
    slow: float


@dataclass(frozen=True)
class OptionSelection:
    symbol: str
    expiration_date: date
    dte: int
    strike: float
    bid: float
    ask: float
    spread_pct: float
    multiplier: int
    quantity: int
    estimated_premium: float


def validate_config(config: StrategyConfig) -> None:
    if not re.match(r"^[A-Z][A-Z0-9.-]{0,7}$", config.underlying):
        raise AgentError("underlying must be an uppercase Alpaca equity symbol.")
    if config.fast_window <= 0 or config.slow_window <= config.fast_window:
        raise AgentError("slow_window must be greater than fast_window and both must be positive.")
    if config.minimum_dte < 6 or config.maximum_dte < config.minimum_dte:
        raise AgentError("Option DTE bounds are invalid; minimum_dte must be at least 6.")
    if not 0 < config.max_position_pct <= 1:
        raise AgentError("max_position_pct must be greater than 0 and at most 1.")
    if config.max_premium <= 0 or config.max_contracts <= 0:
        raise AgentError("max_premium and max_contracts must be positive.")
    if not 0 < config.max_spread_pct <= 1:
        raise AgentError("max_spread_pct must be greater than 0 and at most 1.")
    if not 0 < config.max_daily_loss_pct <= 1:
        raise AgentError("max_daily_loss_pct must be greater than 0 and at most 1.")
    if config.minimum_equity < 0:
        raise AgentError("minimum_equity cannot be negative.")


def load_config(path: str | None) -> StrategyConfig:
    if not path:
        config = StrategyConfig()
        validate_config(config)
        return config
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentError(f"Could not read config file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AgentError(f"Config file {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise AgentError("Config file must contain a JSON object.")
    unknown = sorted(set(raw) - set(asdict(StrategyConfig())))
    if unknown:
        raise AgentError(f"Config contains unsupported fields: {', '.join(unknown)}.")
    try:
        config = StrategyConfig(**raw)
    except TypeError as exc:
        raise AgentError(f"Config contains invalid fields: {exc}") from exc
    validate_config(config)
    return config


def validate_account(account: dict[str, Any], config: StrategyConfig) -> dict[str, Any]:
    status = str(account.get("status", "")).upper()
    if status not in {"ACTIVE", "PAPER_ONLY"}:
        raise AgentBlocked(f"Account status {status or 'unknown'} is not tradable.")
    for field in ("trading_blocked", "account_blocked", "trade_suspended_by_user"):
        if field not in account:
            raise AgentBlocked(f"Could not verify account safety field {field}.")
        if _flag(account[field], field):
            raise AgentBlocked(f"Account safety field {field} is true.")

    equity = _number(account.get("equity"), "equity")
    if equity < config.minimum_equity:
        raise AgentBlocked(
            f"Equity ${equity:,.2f} is below the ${config.minimum_equity:,.2f} demo floor."
        )
    last_equity = _number(account.get("last_equity"), "last_equity")
    if last_equity <= 0:
        raise AgentBlocked("Could not verify daily loss because last_equity is not positive.")
    daily_return = equity / last_equity - 1
    if daily_return <= -config.max_daily_loss_pct:
        raise AgentBlocked(
            f"Daily loss gate triggered at {daily_return:.2%}; "
            f"limit is {-config.max_daily_loss_pct:.2%}."
        )
    options_level = _integer(account.get("options_trading_level"), "options_trading_level")
    if options_level < 2:
        raise AgentBlocked(
            f"Options level {options_level} is insufficient; this strategy requires level 2."
        )
    buying_power = _number(account.get("buying_power"), "buying_power")
    return {
        "account_id": _redact_account_id(account.get("id")),
        "status": status,
        "equity": round(equity, 2),
        "buying_power": round(buying_power, 2),
        "options_trading_level": options_level,
        "daily_return": round(daily_return, 6),
    }


def evaluate_signal(closes: list[float], config: StrategyConfig) -> Signal:
    required = config.slow_window + 1
    if len(closes) < required:
        raise AgentError(
            f"Received {len(closes)} completed bars; {required} are required for the strategy."
        )
    previous = closes[:-1]
    previous_fast = _sma(previous, config.fast_window)
    previous_slow = _sma(previous, config.slow_window)
    fast = _sma(closes, config.fast_window)
    slow = _sma(closes, config.slow_window)
    return Signal(
        triggered=previous_fast <= previous_slow and fast > slow,
        close=closes[-1],
        previous_fast=previous_fast,
        previous_slow=previous_slow,
        fast=fast,
        slow=slow,
    )


def select_option(
    contracts: list[dict[str, Any]],
    underlying_price: float,
    equity: float,
    buying_power: float,
    as_of: date,
    config: StrategyConfig,
) -> OptionSelection:
    max_notional = min(
        config.max_premium,
        equity * config.max_position_pct,
        buying_power,
    )
    target_dte = (config.minimum_dte + config.maximum_dte) // 2
    candidates: list[tuple[tuple[float, float], OptionSelection]] = []

    for contract in contracts:
        symbol = str(contract.get("symbol") or "")
        if not symbol or not _is_option_for(symbol, config.underlying):
            continue
        if str(contract.get("status") or "").lower() != "active":
            continue
        if contract.get("tradable") is not True:
            continue
        contract_type = str(
            contract.get("type") or contract.get("contract_type") or ""
        ).lower()
        if contract_type not in {"call", "c"}:
            continue
        expiration = _date(contract.get("expiration_date"), "expiration_date")
        dte = (expiration - as_of).days
        if not config.minimum_dte <= dte <= config.maximum_dte:
            continue
        strike = _number(contract.get("strike_price"), "strike_price")
        if contract.get("bid_price") is None or contract.get("ask_price") is None:
            continue
        bid = _number(contract["bid_price"], "bid_price")
        ask = _number(contract["ask_price"], "ask_price")
        if bid < 0 or ask <= 0 or bid > ask:
            continue
        spread_pct = (ask - bid) / ask
        if spread_pct > config.max_spread_pct:
            continue
        if contract.get("volume") is None or _number(contract["volume"], "volume") < 1:
            continue
        if contract.get("multiplier") is None:
            raise AgentError("Alpaca option contract did not include multiplier.")
        multiplier = _integer(contract["multiplier"], "contract multiplier")
        if multiplier <= 0:
            continue
        quantity = min(config.max_contracts, math.floor(max_notional / (ask * multiplier)))
        if quantity <= 0:
            continue
        selection = OptionSelection(
            symbol=symbol,
            expiration_date=expiration,
            dte=dte,
            strike=strike,
            bid=bid,
            ask=ask,
            spread_pct=spread_pct,
            multiplier=multiplier,
            quantity=quantity,
            estimated_premium=ask * multiplier * quantity,
        )
        score = (abs(dte - target_dte), abs(strike - underlying_price))
        candidates.append((score, selection))

    if not candidates:
        raise AgentBlocked(
            "No active call passed the DTE, quote, spread, tradability, and budget gates."
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def client_order_id(underlying: str, order_date: date, contract_symbol: str) -> str:
    digest = hashlib.sha256(contract_symbol.encode("utf-8")).hexdigest()[:10]
    return f"hackathon-{underlying.lower()}-{order_date:%Y%m%d}-{digest}"


def build_order(selection: OptionSelection, underlying: str, order_date: date) -> dict[str, Any]:
    return {
        "symbol": selection.symbol,
        "qty": str(selection.quantity),
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "limit_price": f"{selection.ask:.2f}",
        "position_intent": "buy_to_open",
        "client_order_id": client_order_id(underlying, order_date, selection.symbol),
    }


def _close_values(bars: list[dict[str, Any]]) -> list[float]:
    closes = []
    for bar in bars:
        closes.append(_number(bar.get("c"), "bar close"))
    return closes


def _underlying_price(quote: dict[str, Any], fallback: float) -> float:
    ask = quote.get("ap")
    bid = quote.get("bp")
    if ask is not None and bid is not None:
        ask_value = _number(ask, "quote ask")
        bid_value = _number(bid, "quote bid")
        if ask_value > 0 and 0 <= bid_value <= ask_value:
            return (ask_value + bid_value) / 2
    return fallback


def _ensure_no_existing_exposure(
    positions: list[dict[str, Any]],
    open_orders: list[dict[str, Any]],
    underlying: str,
) -> None:
    position = next(
        (
            item
            for item in positions
            if str(item.get("asset_class", "")).lower() in {"us_option", "option"}
            and _is_option_for(item.get("symbol"), underlying)
        ),
        None,
    )
    if position:
        raise AgentBlocked(
            f"An existing {underlying} option position is open; refusing to add exposure."
        )
    order = next(
        (
            item
            for item in open_orders
            if _is_option_for(item.get("symbol"), underlying)
        ),
        None,
    )
    if order:
        raise AgentBlocked(
            f"An existing {underlying} option order is working; refusing a duplicate."
        )


def run_once(client: AlpacaClient, config: StrategyConfig, submit: bool) -> dict[str, Any]:
    validate_paper_environment()
    account = client.account()
    account_summary = validate_account(account, config)
    clock = client.clock()
    market_open = _flag(clock.get("is_open"), "is_open")

    bars = client.daily_bars(config.underlying, config.slow_window + 2)
    signal = evaluate_signal(_close_values(bars), config)
    result: dict[str, Any] = {
        "environment": "PAPER",
        "trading_endpoint": PAPER_TRADING_URL,
        "market_data_endpoint": MARKET_DATA_URL,
        "options_data_feed": "indicative",
        "strategy": "daily_sma_crossover_long_call",
        "config": asdict(config),
        "account": account_summary,
        "market_open": market_open,
        "signal": asdict(signal),
        "disclosure": DISCLOSURE,
    }
    if not signal.triggered:
        result["action"] = "no_trade"
        result["reason"] = "No fresh bullish fast-over-slow SMA crossover."
        return result

    positions = client.positions()
    open_orders = client.open_orders(config.underlying)
    _ensure_no_existing_exposure(positions, open_orders, config.underlying)
    quote = client.latest_quote(config.underlying)
    current_price = _underlying_price(quote, signal.close)
    today = datetime.now(timezone.utc).date()
    contracts = client.option_contracts(
        config.underlying,
        today + timedelta(days=config.minimum_dte),
        today + timedelta(days=config.maximum_dte),
    )
    snapshots = client.option_snapshots(
        [str(contract.get("symbol")) for contract in contracts if contract.get("symbol")]
    )
    contracts_with_quotes = []
    for contract in contracts:
        enriched = dict(contract)
        quote = snapshots.get(str(contract.get("symbol")))
        if quote:
            enriched.update(quote)
        contracts_with_quotes.append(enriched)
    selection = select_option(
        contracts_with_quotes,
        current_price,
        account_summary["equity"],
        account_summary["buying_power"],
        today,
        config,
    )
    order = build_order(selection, config.underlying, today)
    existing = client.order_by_client_id(order["client_order_id"])
    if existing:
        raise AgentBlocked(
            f"Order {order['client_order_id']} already exists; refusing a duplicate."
        )

    result["action"] = "submit" if submit else "preview"
    result["underlying_price"] = round(current_price, 4)
    result["option"] = asdict(selection)
    result["order_preview"] = order
    if not submit:
        result["reason"] = "Dry run; pass --submit only after reviewing this preview."
        return result

    if not market_open:
        raise AgentBlocked("Options market is closed; no order was submitted.")

    # Re-check account state and idempotency immediately before an unattended submit.
    validate_paper_environment()
    final_account = validate_account(client.account(), config)
    if final_account["buying_power"] < selection.estimated_premium:
        raise AgentBlocked("Buying power changed and no longer covers the order premium.")
    if client.order_by_client_id(order["client_order_id"]):
        raise AgentBlocked("The deterministic client order ID already exists; no retry was sent.")
    response = client.submit_order(order)
    result["submitted_order"] = {
        key: response.get(key)
        for key in ("id", "client_order_id", "status", "symbol", "qty", "limit_price", "submitted_at")
        if key in response
    }
    return result


def _print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    print(f"Environment: {result['environment']}")
    print(f"Strategy: {result['strategy']}")
    print(f"Action: {result['action']}")
    if "reason" in result:
        print(f"Reason: {result['reason']}")
    if "option" in result:
        option = result["option"]
        print(
            "Option preview: "
            f"{option['symbol']} x{option['quantity']} at ${option['ask']:.2f}, "
            f"estimated premium ${option['estimated_premium']:.2f}"
        )
    if "submitted_order" in result:
        print(f"Submitted order: {result['submitted_order']}")
    print(result["disclosure"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="JSON strategy configuration file")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit the reviewed order to the pinned Alpaca paper endpoint",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--loop-seconds",
        type=int,
        default=0,
        help="Repeat after this many seconds; default is one run",
    )
    args = parser.parse_args(argv)
    if args.loop_seconds < 0:
        parser.error("--loop-seconds cannot be negative")

    try:
        config = load_config(args.config)
        key, secret = credentials_from_environment()
        client = AlpacaClient(key, secret)
        while True:
            result = run_once(client, config, args.submit)
            _print_result(result, args.json)
            if args.loop_seconds == 0:
                return 0
            time.sleep(args.loop_seconds)
    except AgentError as exc:
        if args.json:
            print(
                json.dumps(
                    {"environment": "PAPER", "action": "blocked", "error": str(exc)},
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
