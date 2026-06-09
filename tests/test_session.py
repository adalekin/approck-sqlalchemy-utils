import approck_sqlalchemy_utils.session as db
from approck_sqlalchemy_utils.mocks import _unconfigured_get_session


def test_override_session_is_tuple_for_dependency_overrides() -> None:
    override_key, override_dep = db.override_session

    assert override_key is _unconfigured_get_session
    assert callable(override_dep)

    overrides: dict[object, object] = {}
    overrides.setdefault(*db.override_session)

    assert overrides[override_key] is override_dep
