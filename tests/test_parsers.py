from approck_sqlalchemy_utils.parsers import order_by


def test_order_by_parse_quotes_reserved_word():
    clauses = order_by.parse(["order:asc"])

    assert len(clauses) == 1
    assert str(clauses[0]) == '"order" asc'


def test_order_by_parse_quotes_regular_field():
    clauses = order_by.parse(["name:desc"])

    assert len(clauses) == 1
    assert str(clauses[0]) == '"name" desc'
