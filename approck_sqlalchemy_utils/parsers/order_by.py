from typing import List

from sqlalchemy import TextClause, text


def parse(raw_orders: List[str]) -> List[TextClause]:
    order_clauses = []

    for raw_order in raw_orders:
        order, direction = raw_order.split(":", 1)
        quoted_order = ".".join(f'"{part}"' for part in order.split("."))
        order_clauses.append(text(f"{quoted_order} {direction}"))

    return order_clauses
