"""Local paper-trading ledger with rationale-first trade journaling."""

from __future__ import annotations

import hashlib
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from portfolio_research.audit import append_audit_event
from portfolio_research.config import PROJECT_ROOT
from portfolio_research.market_data import validate_symbols

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "paper_trading.sqlite3"
DEFAULT_ACCOUNT_ID = "default"


@dataclass(frozen=True)
class PaperTrade:
    """A simulated trade and its optional post-trade review."""

    trade_id: int
    created_at: str
    symbol: str
    side: str
    quantity: float
    reference_price: float
    cost_rate: float
    rationale: str
    review: str | None


@dataclass(frozen=True)
class PaperPortfolio:
    """Cash, current simulated holdings, and the account's journal entries."""

    initial_cash: float
    cash: float
    holdings: tuple[tuple[str, float], ...]
    cumulative_costs: float
    trades: tuple[PaperTrade, ...]


def _validate_positive_finite(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive.")
    return float(value)


def _validate_account_id(account_id: str) -> str:
    if not isinstance(account_id, str):
        raise TypeError("Paper account ID must be a string.")
    normalized = account_id.strip()
    if not normalized or len(normalized) > 100:
        raise ValueError("Paper account ID must contain 1 to 100 characters.")
    return normalized


def _connect(database_path: Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_accounts (
            account_id TEXT PRIMARY KEY,
            initial_cash REAL NOT NULL CHECK (initial_cash > 0),
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL REFERENCES paper_accounts(account_id),
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
            quantity REAL NOT NULL CHECK (quantity > 0),
            reference_price REAL NOT NULL CHECK (reference_price > 0),
            cost_rate REAL NOT NULL CHECK (cost_rate >= 0),
            rationale TEXT NOT NULL,
            review TEXT
        )
        """
    )
    connection.commit()
    return connection


def _trade_from_row(row: sqlite3.Row) -> PaperTrade:
    return PaperTrade(
        trade_id=row["trade_id"],
        created_at=row["created_at"],
        symbol=row["symbol"],
        side=row["side"],
        quantity=row["quantity"],
        reference_price=row["reference_price"],
        cost_rate=row["cost_rate"],
        rationale=row["rationale"],
        review=row["review"],
    )


def load_paper_portfolio(
    database_path: Path = DEFAULT_DATABASE_PATH,
    account_id: str = DEFAULT_ACCOUNT_ID,
    initial_cash: float = 10_000.0,
) -> PaperPortfolio:
    """Load an account, creating a local paper account if it does not exist."""
    validated_account = _validate_account_id(account_id)
    validated_cash = _validate_positive_finite(initial_cash, "Initial cash")
    with closing(_connect(database_path)) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO paper_accounts (account_id, initial_cash, created_at)
            VALUES (?, ?, ?)
            """,
            (validated_account, validated_cash, datetime.now(UTC).isoformat()),
        )
        connection.commit()
        account = connection.execute(
            "SELECT initial_cash FROM paper_accounts WHERE account_id = ?",
            (validated_account,),
        ).fetchone()
        if account is None:
            raise RuntimeError("Paper account could not be loaded.")
        trade_rows = connection.execute(
            """
            SELECT trade_id, created_at, symbol, side, quantity, reference_price,
                   cost_rate, rationale, review
            FROM paper_trades
            WHERE account_id = ?
            ORDER BY trade_id
            """,
            (validated_account,),
        ).fetchall()

    trades = tuple(_trade_from_row(row) for row in trade_rows)
    cash = float(account["initial_cash"])
    holdings: dict[str, float] = {}
    cumulative_costs = 0.0
    for trade in trades:
        notional = trade.quantity * trade.reference_price
        costs = notional * trade.cost_rate
        cumulative_costs += costs
        holdings[trade.symbol] = holdings.get(trade.symbol, 0.0) + (
            trade.quantity if trade.side == "buy" else -trade.quantity
        )
        cash += -notional - costs if trade.side == "buy" else notional - costs
    cleaned_holdings = tuple(
        (symbol, quantity)
        for symbol, quantity in sorted(holdings.items())
        if not math.isclose(quantity, 0.0, abs_tol=1e-10)
    )
    return PaperPortfolio(
        initial_cash=float(account["initial_cash"]),
        cash=cash,
        holdings=cleaned_holdings,
        cumulative_costs=cumulative_costs,
        trades=trades,
    )


def record_paper_trade(
    symbol: str,
    side: str,
    quantity: float,
    reference_price: float,
    rationale: str,
    transaction_cost_bps_per_side: float,
    slippage_bps_per_side: float,
    database_path: Path = DEFAULT_DATABASE_PATH,
    account_id: str = DEFAULT_ACCOUNT_ID,
    initial_cash: float = 10_000.0,
) -> PaperTrade:
    """Record a simulated order only when rationale and account limits validate."""
    normalized_symbol = validate_symbols([symbol])[0]
    normalized_side = side.strip().lower() if isinstance(side, str) else ""
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("Paper trade side must be 'buy' or 'sell'.")
    validated_quantity = _validate_positive_finite(quantity, "Quantity")
    validated_price = _validate_positive_finite(reference_price, "Reference price")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("Record the reasoning before placing a paper trade.")
    if len(rationale.strip()) > 5_000:
        raise ValueError("Trade rationale must be at most 5,000 characters.")
    cost_values = (transaction_cost_bps_per_side, slippage_bps_per_side)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        for value in cost_values
    ):
        raise ValueError(
            "Transaction cost and slippage must be finite and non-negative."
        )
    cost_rate = sum(cost_values) / 10_000
    if cost_rate >= 1:
        raise ValueError("Combined cost and slippage must be less than 10,000 bps.")
    validated_account = _validate_account_id(account_id)
    validated_cash = _validate_positive_finite(initial_cash, "Initial cash")
    now = datetime.now(UTC).isoformat()

    with closing(_connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO paper_accounts
                    (account_id, initial_cash, created_at)
                VALUES (?, ?, ?)
                """,
                (validated_account, validated_cash, now),
            )
            account = connection.execute(
                "SELECT initial_cash FROM paper_accounts WHERE account_id = ?",
                (validated_account,),
            ).fetchone()
            if account is None:
                raise RuntimeError("Paper account could not be initialized.")
            rows = connection.execute(
                """
                SELECT symbol, side, quantity, reference_price, cost_rate
                FROM paper_trades WHERE account_id = ?
                """,
                (validated_account,),
            ).fetchall()
            cash = float(account["initial_cash"])
            current_quantity = 0.0
            for row in rows:
                notional = row["quantity"] * row["reference_price"]
                fee = notional * row["cost_rate"]
                cash += -notional - fee if row["side"] == "buy" else notional - fee
                if row["symbol"] == normalized_symbol:
                    current_quantity += (
                        row["quantity"] if row["side"] == "buy" else -row["quantity"]
                    )

            notional = validated_quantity * validated_price
            fees = notional * cost_rate
            if normalized_side == "buy" and notional + fees > cash:
                raise ValueError("Insufficient paper cash for this trade and costs.")
            if normalized_side == "sell" and validated_quantity > current_quantity:
                raise ValueError(
                    "Cannot sell more shares than the paper account holds."
                )

            cursor = connection.execute(
                """
                INSERT INTO paper_trades (
                    account_id, created_at, symbol, side, quantity, reference_price,
                    cost_rate, rationale, review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    validated_account,
                    now,
                    normalized_symbol,
                    normalized_side,
                    validated_quantity,
                    validated_price,
                    cost_rate,
                    rationale.strip(),
                ),
            )
            trade_id = int(cursor.lastrowid)
            append_audit_event(
                "paper_trade_attempted",
                {
                    "trade_id": trade_id,
                    "symbol": normalized_symbol,
                    "side": normalized_side,
                    "quantity": validated_quantity,
                    "reference_price": validated_price,
                    "cost_rate": cost_rate,
                    "rationale_sha256": hashlib.sha256(
                        rationale.strip().encode("utf-8")
                    ).hexdigest(),
                },
            )

    return PaperTrade(
        trade_id=trade_id,
        created_at=now,
        symbol=normalized_symbol,
        side=normalized_side,
        quantity=validated_quantity,
        reference_price=validated_price,
        cost_rate=cost_rate,
        rationale=rationale.strip(),
        review=None,
    )


def add_trade_review(
    trade_id: int,
    review: str,
    database_path: Path = DEFAULT_DATABASE_PATH,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> None:
    """Attach an honest post-trade reflection to an existing journal entry."""
    if isinstance(trade_id, bool) or not isinstance(trade_id, int) or trade_id <= 0:
        raise ValueError("Trade ID must be a positive integer.")
    if not isinstance(review, str) or not review.strip():
        raise ValueError("Post-trade review must not be empty.")
    if len(review.strip()) > 5_000:
        raise ValueError("Post-trade review must be at most 5,000 characters.")
    validated_account = _validate_account_id(account_id)
    with closing(_connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        with connection:
            cursor = connection.execute(
                """
                UPDATE paper_trades SET review = ?
                WHERE trade_id = ? AND account_id = ?
                """,
                (review.strip(), trade_id, validated_account),
            )
            if cursor.rowcount != 1:
                raise ValueError("No paper trade with that ID exists in this account.")
            append_audit_event(
                "paper_trade_reviewed",
                {
                    "trade_id": trade_id,
                    "review_sha256": hashlib.sha256(
                        review.strip().encode("utf-8")
                    ).hexdigest(),
                },
            )
