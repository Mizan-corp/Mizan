"""Step 11b: publishing needs the developer's yes to the current terms; signing up and the CLI stay open."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import main  # noqa: F401  (settings)
from app.platform.developers import service


def test_a_developer_who_never_accepted_cannot_publish():
    with pytest.raises(HTTPException) as e:
        service.require_terms(SimpleNamespace(terms_version=None))
    assert e.value.status_code == 403


def test_an_older_terms_version_must_be_accepted_again():
    with pytest.raises(HTTPException):
        service.require_terms(SimpleNamespace(terms_version="2000-01"))


def test_accepting_the_current_terms_allows_publishing():
    service.require_terms(SimpleNamespace(terms_version=service.TERMS_VERSION))


def test_the_columns_and_the_migration_exist():
    from app.db.migrations import MIGRATIONS
    from app.platform.developers.models import DeveloperUser

    assert hasattr(DeveloperUser, "terms_version") and hasattr(DeveloperUser, "terms_accepted_at")
    sql = dict(MIGRATIONS)["v124_developer_terms"]
    assert "terms_version" in sql and "terms_accepted_at" in sql and "DROP" not in sql.upper()
