"""Read-only hub card for Repo Reality Check orders and revenue.

Built only on the ``OrderBook`` read path (``get`` / ``orders`` /
``revenue_summary``). The card never creates, confirms, fulfills, delivers,
refunds, or fails an order, performs no payment, and uses no network.
Opening the book may refresh its cached ``orders.json`` projection; that is
the base module's own read-path repair, not a card write — no receipt is
appended and no order changes status.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from courier_core.reality_orders import (
    CURRENCY,
    PRICE_CENTS,
    PRODUCT,
    STATUSES,
    OrderBook,
)

_ROW_KEYS = (
    "order_id",
    "product",
    "price_cents",
    "currency",
    "repo_ref",
    "status",
    "payment_evidence",
    "delivery_evidence",
    "refund_evidence",
    "failure_evidence",
    "ready_evidence",
)


def _row(order: Mapping[str, Any]) -> dict[str, Any]:
    """One card row. Contact material is never carried onto the card."""
    return {key: order.get(key) for key in _ROW_KEYS}


def revenue_card_from_book(book: OrderBook) -> dict[str, Any]:
    """Render the card from an already-open book. Reads only."""
    orders = [_row(order) for order in book.orders()]
    counts = {status: 0 for status in sorted(STATUSES)}
    for order in orders:
        counts[order["status"]] += 1
    summary = book.revenue_summary()
    return {
        "product": PRODUCT,
        "price_cents": PRICE_CENTS,
        "currency": CURRENCY,
        "counts": counts,
        "order_count": len(orders),
        "orders": orders,
        "revenue": summary,
    }


def revenue_card(directory: str | os.PathLike) -> dict[str, Any]:
    """Render the card for the order book in ``directory``. Reads only."""
    return revenue_card_from_book(OrderBook(directory))
