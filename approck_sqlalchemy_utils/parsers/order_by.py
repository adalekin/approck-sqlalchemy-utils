import re
from typing import List

from sqlalchemy import TextClause, text

# ORDER BY reaches raw SQL through text(), so every part is validated before it is
# interpolated. Field segments must be plain identifiers (no embedded quotes that could
# close the quoting and break out); the direction is restricted to a fixed whitelist.
# Without this the text after the ":" was passed through verbatim, so a value like
# "id:asc/**/...", "id:asc--" or "id:asc nulls last" injected arbitrary SQL into the
# ORDER BY clause, and a field like 'a"b' broke out of the identifier quoting.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DIRECTIONS = frozenset({"asc", "desc"})


def parse(raw_orders: List[str]) -> List[TextClause]:
    order_clauses = []

    for raw_order in raw_orders:
        field, separator, raw_direction = raw_order.partition(":")
        if not separator:
            raise ValueError(f"Invalid order_by clause {raw_order!r}: expected '<field>:<asc|desc>'")

        direction = raw_direction.strip().lower()
        if direction not in _DIRECTIONS:
            raise ValueError(f"Invalid order_by direction {raw_direction!r}: expected one of 'asc', 'desc'")

        parts = field.split(".")
        if not all(_IDENTIFIER_RE.match(part) for part in parts):
            raise ValueError(f"Invalid order_by field {field!r}: each segment must be a plain identifier")

        quoted_order = ".".join(f'"{part}"' for part in parts)
        order_clauses.append(text(f"{quoted_order} {direction}"))

    return order_clauses
