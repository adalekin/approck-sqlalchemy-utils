"""Tests for the custom SQLAlchemy types and encryption engines.

These exercise pure Python surfaces (engines, padding, TypeDecorator hooks) with a
stub dialect, so they need no database. The property tests on the engines pin the
behaviour StringEncryptedType relies on: AesEngine is deterministic (searchable),
AesGcmEngine is randomised — a regression in either must fail loudly.
"""

from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from approck_sqlalchemy_utils.types.encrypted.encrypted_type import (
    AesEngine,
    AesGcmEngine,
    FernetEngine,
    InvalidCiphertextError,
    StringEncryptedType,
)
from approck_sqlalchemy_utils.types.encrypted.padding import (
    InvalidPaddingError,
    NaivePadding,
    OneAndZeroesPadding,
    PKCS5Padding,
    ZeroesPadding,
)
from approck_sqlalchemy_utils.types.json import JSONType
from approck_sqlalchemy_utils.types.scalar_list import ScalarListException, ScalarListType

_SQLITE = SimpleNamespace(name="sqlite")
_POSTGRES = SimpleNamespace(name="postgresql")


# --- Encryption engines -----------------------------------------------------


def _aes():
    engine = AesEngine()
    engine._set_padding_mechanism("pkcs5")
    engine._update_key("secret-key")
    return engine


def test_aes_engine_round_trip():
    engine = _aes()
    assert engine.decrypt(engine.encrypt("привет мир")) == "привет мир"


def test_aes_engine_is_deterministic():
    # Key-derived IV in CBC: equal plaintext -> equal ciphertext. This is what makes
    # searching by an encrypted value work; pin it so an accidental IV change is caught.
    engine = _aes()
    assert engine.encrypt("same") == engine.encrypt("same")


def test_aes_gcm_engine_round_trip():
    engine = AesGcmEngine()
    engine._update_key("secret-key")
    assert engine.decrypt(engine.encrypt("привет мир")) == "привет мир"


def test_aes_gcm_engine_is_randomised():
    # Random per-value IV: equal plaintext -> different ciphertext.
    engine = AesGcmEngine()
    engine._update_key("secret-key")
    assert engine.encrypt("same") != engine.encrypt("same")


def test_aes_gcm_engine_rejects_truncated_ciphertext():
    engine = AesGcmEngine()
    engine._update_key("secret-key")
    with pytest.raises(InvalidCiphertextError):
        engine.decrypt("QUJD")  # base64 for "ABC": shorter than iv + tag


def test_fernet_engine_round_trip():
    engine = FernetEngine()
    engine._update_key("secret-key")
    assert engine.decrypt(engine.encrypt("привет мир")) == "привет мир"


# --- Padding mechanisms ------------------------------------------------------


@pytest.mark.parametrize("padding_cls", [PKCS5Padding, OneAndZeroesPadding, ZeroesPadding, NaivePadding])
@pytest.mark.parametrize("payload", [b"", b"a", b"0123456789", b"exactly-16-bytes", b"seventeen-bytes!!"])
def test_padding_round_trip(padding_cls, payload):
    padding = padding_cls(16)
    padded = padding.pad(payload)
    assert len(padded) % 16 == 0
    assert padding.unpad(padded) == payload


def test_pkcs5_unpad_rejects_short_block():
    with pytest.raises(InvalidPaddingError):
        PKCS5Padding(16).unpad(b"too-short")


def test_pkcs5_unpad_rejects_bad_padding_byte():
    # Last byte claims a padding length the trailing bytes don't back up.
    with pytest.raises(InvalidPaddingError):
        PKCS5Padding(16).unpad(b"0123456789012345" + bytes([16] * 15 + [7]))


# --- StringEncryptedType (TypeDecorator hooks) -------------------------------


def _encrypted(type_in):
    column_type = StringEncryptedType(type_in, "secret-key")
    return column_type


@pytest.mark.parametrize(
    "type_in, value",
    [
        (sa.Unicode, "текст"),
        (sa.Integer, 42),
        (sa.Boolean, True),
        (sa.Boolean, False),
    ],
)
def test_string_encrypted_type_round_trip(type_in, value):
    column_type = _encrypted(type_in)
    stored = column_type.process_bind_param(value, _SQLITE)
    assert stored != value  # actually encrypted
    assert column_type.process_result_value(stored, _SQLITE) == value


def test_string_encrypted_type_passes_none_through():
    column_type = _encrypted(sa.Unicode)
    assert column_type.process_bind_param(None, _SQLITE) is None
    assert column_type.process_result_value(None, _SQLITE) is None


# --- JSONType ----------------------------------------------------------------


def test_json_type_sqlite_serialises_to_text():
    json_type = JSONType()
    payload = {"color": "red", "n": 3}
    stored = json_type.process_bind_param(payload, _SQLITE)
    assert isinstance(stored, str)
    assert json_type.process_result_value(stored, _SQLITE) == payload


def test_json_type_postgres_passes_native():
    json_type = JSONType()
    payload = {"color": "red"}
    # On PostgreSQL the native json type stores the value directly.
    assert json_type.process_bind_param(payload, _POSTGRES) == payload


# --- ScalarListType ----------------------------------------------------------


def test_scalar_list_round_trip_strings():
    column_type = ScalarListType()
    stored = column_type.process_bind_param(["football", "ice_hockey"], _SQLITE)
    assert stored == "football,ice_hockey"
    assert column_type.process_result_value(stored, _SQLITE) == ["football", "ice_hockey"]


def test_scalar_list_round_trip_ints():
    column_type = ScalarListType(int)
    stored = column_type.process_bind_param([1, 2, 3], _SQLITE)
    assert column_type.process_result_value(stored, _SQLITE) == [1, 2, 3]


def test_scalar_list_empty_string_is_empty_list():
    assert ScalarListType().process_result_value("", _SQLITE) == []


def test_scalar_list_rejects_value_containing_separator():
    with pytest.raises(ScalarListException):
        ScalarListType().process_bind_param(["a,b"], _SQLITE)
