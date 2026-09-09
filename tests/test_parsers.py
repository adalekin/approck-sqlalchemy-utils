import pytest

from approck_sqlalchemy_utils.parsers import order_by


def test_order_by_parse_quotes_reserved_word():
    clauses = order_by.parse(["order:asc"])

    assert len(clauses) == 1
    assert str(clauses[0]) == '"order" asc'


def test_order_by_parse_quotes_regular_field():
    clauses = order_by.parse(["name:desc"])

    assert len(clauses) == 1
    assert str(clauses[0]) == '"name" desc'


def test_order_by_parse_quotes_table_qualified_field():
    clauses = order_by.parse(["generation_candidate.id:desc"])

    assert len(clauses) == 1
    assert str(clauses[0]) == '"generation_candidate"."id" desc'


def test_order_by_parse_normalizes_direction_case():
    clauses = order_by.parse(["name:DESC"])

    assert str(clauses[0]) == '"name" desc'


@pytest.mark.parametrize(
    "raw_order",
    [
        "id:asc/**/limit/**/1",  # trailing SQL smuggled after the direction
        "id:asc--",  # comment tail
        "id:asc nulls last",  # extra clause never on the whitelist
        "id:asc;drop table author",  # statement injection
    ],
)
def test_order_by_rejects_sql_in_direction(raw_order):
    with pytest.raises(ValueError):
        order_by.parse([raw_order])


@pytest.mark.parametrize(
    "raw_order",
    [
        'a"b:asc',  # embedded quote would break out of the identifier quoting
        "id);select 1:asc",
        "*:asc",
        ":asc",  # empty field
    ],
)
def test_order_by_rejects_non_identifier_field(raw_order):
    with pytest.raises(ValueError):
        order_by.parse([raw_order])


def test_order_by_rejects_missing_direction():
    with pytest.raises(ValueError):
        order_by.parse(["id"])
