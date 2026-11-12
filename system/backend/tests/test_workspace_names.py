"""A workspace's URL name is also its subdomain (ADR-008): a DNS label, not a platform name."""
import pytest
from fastapi import HTTPException

from app.platform.tenancy.service import RESERVED_SLUGS, check_slug, slugify


@pytest.mark.parametrize("slug", ["acme", "monset-gym", "a1b", "x" * 48])
def test_valid_names(slug):
    assert check_slug(slug) == slug


@pytest.mark.parametrize("slug", ["ab", "-acme", "acme-", "Acme", "ac_me", "ac.me", "x" * 49, ""])
def test_invalid_names(slug):
    with pytest.raises(HTTPException) as e:
        check_slug(slug)
    assert e.value.status_code == 422


@pytest.mark.parametrize("slug", sorted(RESERVED_SLUGS - {"c"}))
def test_reserved_names_are_refused(slug):
    with pytest.raises(HTTPException):
        check_slug(slug)


def test_generated_names_are_valid_labels():
    for name in ("Acme Trading", "صيدلية النور", "--x--", "A" * 80):
        assert check_slug(slugify(name))
