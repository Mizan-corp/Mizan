"""Step 12a: an owner restyles a workspace only with fonts and colours Mizan ships."""
import main  # noqa: F401  (settings)
from app.platform.themes import service


def test_a_font_the_platform_does_not_ship_is_dropped():
    known = next(iter(service.family_files()))
    assert service.check_font_choice({"body": "Comic Evil", "display": "../../etc/passwd"}) == {}
    assert service.check_font_choice({"body": known}) == {"body": known}


def test_only_body_and_display_can_be_set():
    known = next(iter(service.family_files()))
    assert service.check_font_choice({"body": known, "mono": known, "css": "x{}"}) == {"body": known}


def test_a_font_choice_that_is_not_a_mapping_is_ignored():
    for bad in (None, "Cairo", ["body"], 3):
        assert service.check_font_choice(bad) == {}


def test_a_palette_the_platform_does_not_ship_is_refused():
    pid = next(iter(service.palette_registry()))
    assert service.check_palette_choice(pid) == pid
    for bad in ("#ff0000", "nope", None, 5, "<script>"):
        assert service.check_palette_choice(bad) is None
