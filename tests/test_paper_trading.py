import pytest

from portfolio_research import paper_trading
from portfolio_research.audit import verify_audit_log
from portfolio_research.paper_trading import (
    add_trade_review,
    load_paper_portfolio,
    record_paper_trade,
)


@pytest.fixture(autouse=True)
def isolate_paper_trade_audit(monkeypatch, tmp_path) -> None:
    append_audit_event = paper_trading.append_audit_event
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(
        paper_trading,
        "append_audit_event",
        lambda event_type, payload: append_audit_event(event_type, payload, audit_path),
    )


def test_paper_trades_apply_costs_and_preserve_pre_and_post_trade_notes(
    tmp_path,
) -> None:
    database_path = tmp_path / "paper.sqlite3"
    first = record_paper_trade(
        symbol="spy",
        side="buy",
        quantity=2,
        reference_price=100,
        rationale="Buy the ETF to test a diversified paper allocation.",
        transaction_cost_bps_per_side=10,
        slippage_bps_per_side=20,
        database_path=database_path,
        initial_cash=1_000,
    )
    record_paper_trade(
        symbol="SPY",
        side="sell",
        quantity=1,
        reference_price=110,
        rationale="Reduce one share after reviewing the allocation thesis.",
        transaction_cost_bps_per_side=10,
        slippage_bps_per_side=20,
        database_path=database_path,
        initial_cash=1_000,
    )
    add_trade_review(
        first.trade_id,
        "The trade followed the written plan; review market movement separately.",
        database_path=database_path,
    )

    portfolio = load_paper_portfolio(database_path=database_path, initial_cash=2_000)

    assert portfolio.initial_cash == 1_000
    assert portfolio.cash == pytest.approx(909.07)
    assert portfolio.holdings == (("SPY", 1.0),)
    assert portfolio.cumulative_costs == pytest.approx(0.93)
    assert portfolio.trades[0].review.startswith("The trade followed")
    assert portfolio.trades[0].rationale.startswith("Buy the ETF")
    assert verify_audit_log(tmp_path / "audit.jsonl") == 3


def test_paper_ledger_rejects_unfunded_buys_and_overselling(tmp_path) -> None:
    database_path = tmp_path / "paper.sqlite3"
    with pytest.raises(ValueError, match="Insufficient paper cash"):
        record_paper_trade(
            "SPY",
            "buy",
            2,
            100,
            "A documented rationale for a larger order.",
            5,
            5,
            database_path=database_path,
            initial_cash=100,
        )
    assert not load_paper_portfolio(
        database_path=database_path, initial_cash=100
    ).trades

    record_paper_trade(
        "SPY",
        "buy",
        1,
        50,
        "A documented rationale for this small position.",
        5,
        5,
        database_path=database_path,
        initial_cash=100,
    )
    with pytest.raises(ValueError, match="Cannot sell more shares"):
        record_paper_trade(
            "SPY",
            "sell",
            2,
            50,
            "A documented reason to exit the position.",
            5,
            5,
            database_path=database_path,
            initial_cash=100,
        )


@pytest.mark.parametrize(
    ("symbol", "side", "quantity", "price", "rationale"),
    [
        ("SPY!", "buy", 1, 100, "A valid written rationale for this trade."),
        ("SPY", "short", 1, 100, "A valid written rationale for this trade."),
        ("SPY", "buy", 0, 100, "A valid written rationale for this trade."),
        ("SPY", "buy", 1, float("nan"), "A valid written rationale for this trade."),
        ("SPY", "buy", 1, 100, " "),
    ],
)
def test_paper_ledger_validates_trade_inputs(
    tmp_path, symbol, side, quantity, price, rationale
) -> None:
    with pytest.raises((TypeError, ValueError)):
        record_paper_trade(
            symbol,
            side,
            quantity,
            price,
            rationale,
            5,
            5,
            database_path=tmp_path / "paper.sqlite3",
        )


def test_review_requires_an_existing_trade_and_nonempty_text(tmp_path) -> None:
    database_path = tmp_path / "paper.sqlite3"
    with pytest.raises(ValueError, match="must not be empty"):
        add_trade_review(1, " ", database_path=database_path)
    with pytest.raises(ValueError, match="No paper trade"):
        add_trade_review(1, "Review", database_path=database_path)
