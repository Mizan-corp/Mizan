"""Step 9a: a package's file extension says its kind, and a mismatch is refused."""
import pytest

from app.framework import package as mzm


def test_each_kind_has_its_own_extension():
    assert mzm.extension_for("community") == ".mzmo"
    assert mzm.extension_for("activity") == ".mzba"
    assert mzm.extension_for("theme") == ".mzth"
    assert len(set(mzm.EXTENSIONS.values())) == len(mzm.EXTENSIONS)
    assert mzm.LEGACY_EXTENSION not in mzm.EXTENSIONS.values()


def test_an_unknown_kind_has_no_extension():
    with pytest.raises(mzm.PackageError):
        mzm.extension_for("site_template")


@pytest.mark.parametrize("name, kind", [
    ("visits.mzmo", "community"), ("clinic.MZBA", "activity"), ("dark.mzth", "theme"),
    ("old.mzm", "community"), ("old.mzm", "theme"), ("old.mzm", "activity"),  # the older name holds any kind
    ("pack.zip", "community"), ("noext", "theme"), (None, "activity"), ("", "community"),
])
def test_names_that_fit_are_accepted(name, kind):
    mzm.check_filename(name, kind)


@pytest.mark.parametrize("name, kind", [
    ("visits.mzmo", "theme"), ("visits.mzmo", "activity"), ("dark.mzth", "community"),
    ("clinic.mzba", "community"), ("clinic.mzba", "theme"), ("A.MZMO", "activity"),
])
def test_a_name_for_another_kind_is_refused(name, kind):
    with pytest.raises(mzm.PackageError):
        mzm.check_filename(name, kind)
