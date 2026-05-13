from typing import List

from sqlalchemy import text, TextClause


def parse(raw_orders: List[str]) -> List[TextClause]:
    order_clauses = []

    for raw_order in raw_orders:
        order, direction = raw_order.split(":", 1)
        order_clauses.append(text(f"{order} {direction}"))

    return order_clauses
