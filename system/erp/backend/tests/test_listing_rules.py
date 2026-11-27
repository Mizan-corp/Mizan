"""Step 11a: launch rules for listings. Free only; text changes reach the store only through review."""
import inspect

import pytest

import main  # noqa: F401  (settings)
from app.platform.marketplace import listings


@pytest.mark.parametrize("key", listings.PAID_KEYS)
def test_a_manifest_that_asks_for_money_is_refused(key):
    assert listings.listing_problems({"id": "acme.x", key: 5})


def test_a_free_manifest_has_no_problems():
    assert listings.listing_problems({"id": "acme.x", "name": "x", "version": "1.0.0"}) == []


def test_submit_checks_the_price_rule_before_review():
    assert "listing_problems(pkg.manifest)" in inspect.getsource(listings.submit)


def test_a_listing_changes_its_text_only_when_a_version_is_approved():
    """Name and description are written in approve() alone, so every text edit waits for a human review."""
    src = inspect.getsource(listings)
    assert src.count("item.description =") == 1 and "item.description = m.get(" in inspect.getsource(listings.approve)
    assert src.count("item.name, item.name_en =") == 1 and "item.name, item.name_en =" in inspect.getsource(listings.approve)
