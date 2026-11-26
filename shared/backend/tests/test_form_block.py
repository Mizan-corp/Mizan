"""The form block (contact-form V1): registry validation and the two render modes.

Live only when a hosting runtime passes form_action_base: the public visitor
route does, so a published page carries a working native POST form. Everywhere
else - studio preview, exports - the same tree renders inert: no <form>, a
disabled button, so a block can never post anywhere unintended.
"""
import unittest

from app.framework.manifest import page_problems
from app.platform.site.render import render_page


def form_tree(form_settings=None, form_content=None, form_id="n_form01"):
    return {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_cols01", "type": "columns", "settings": {"desktop": {}}, "content": {},
            "children": [{
                "id": "n_col001", "type": "column", "settings": {}, "content": {},
                "children": [{
                    "id": form_id, "type": "form",
                    "settings": {"desktop": form_settings or {}},
                    "content": {"en": form_content or {}},
                }],
            }],
        }],
    }


FULL_CONTENT = {"title": "Contact us", "name_label": "Name", "email_label": "Email",
                "phone_label": "Phone", "message_label": "Message", "submit_label": "Send",
                "success_message": "Thanks!"}


class FormValidation(unittest.TestCase):
    def test_a_well_formed_form_validates(self):
        self.assertEqual(page_problems(form_tree(), languages=("en",)), [])
        self.assertEqual(page_problems(
            form_tree({"field_name": True, "field_phone": True, "align": "center"}, FULL_CONTENT),
            languages=("en",)), [])

    def test_b_unknown_settings_and_bad_choices_are_rejected(self):
        for bad_settings in ({"align": "middle"}, {"field_name": "yes"}, {"action": "https://x"}):
            self.assertNotEqual(page_problems(form_tree(bad_settings), languages=("en",)), [], bad_settings)

    def test_c_overlong_content_is_rejected(self):
        self.assertNotEqual(page_problems(form_tree({}, {"title": "x" * 121}), languages=("en",)), [])
        self.assertNotEqual(page_problems(form_tree({}, {"submit_label": "x" * 41}), languages=("en",)), [])


class InertRender(unittest.TestCase):
    def test_d_no_action_base_renders_no_form_tag(self):
        html = render_page(form_tree({}, FULL_CONTENT), lang="en")
        self.assertNotIn("<form", html)
        self.assertIn("mz-form-inert", html)
        self.assertIn("disabled", html)
        # Fields and labels still show so the preview matches the live page.
        self.assertIn("Email", html)
        self.assertIn('type="email"', html)

    def test_e_success_message_stays_hidden_without_form_sent(self):
        html = render_page(form_tree({}, FULL_CONTENT), lang="en")
        self.assertNotIn("Thanks!", html)


class LiveRender(unittest.TestCase):
    BASE = "/forms/mysite/contact"

    def test_f_action_base_renders_a_post_form_to_the_node_url(self):
        html = render_page(form_tree({}, FULL_CONTENT), lang="en", form_action_base=self.BASE)
        self.assertIn('<form class="mz-form" method="post"', html)
        self.assertIn(f'action="{self.BASE}/n_form01?lang=en"', html)
        self.assertNotIn("mz-form-inert", html)
        self.assertIn('type="submit"', html)

    def test_g_honeypot_is_rendered_hidden(self):
        html = render_page(form_tree({}, FULL_CONTENT), lang="en", form_action_base=self.BASE)
        self.assertIn('name="website"', html)
        self.assertIn('class="mz-form-hp"', html)
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-form-hp{display:none}", _BASE_CSS)

    def test_h_field_toggles_match_settings(self):
        html = render_page(form_tree({"field_name": True, "field_phone": True}, FULL_CONTENT),
                           lang="en", form_action_base=self.BASE)
        self.assertIn('name="name"', html)
        self.assertIn('name="phone"', html)
        html = render_page(form_tree({}, FULL_CONTENT), lang="en", form_action_base=self.BASE)
        self.assertNotIn('name="name"', html)
        self.assertNotIn('name="phone"', html)
        # email and message are always on.
        self.assertIn('name="email"', html)
        self.assertIn('name="message"', html)

    def test_i_form_sent_shows_the_success_message(self):
        html = render_page(form_tree({}, FULL_CONTENT), lang="en",
                           form_action_base=self.BASE, form_sent="n_form01")
        self.assertIn("Thanks!", html)
        self.assertIn('role="status"', html)
        # A form_sent for another node does not leak into this one.
        html = render_page(form_tree({}, FULL_CONTENT), lang="en",
                           form_action_base=self.BASE, form_sent="n_other9")
        self.assertNotIn("Thanks!", html)

    def test_j_labels_are_escaped(self):
        html = render_page(form_tree({}, {"title": '<img src=x onerror="alert(1)">'}, ),
                           lang="en", form_action_base=self.BASE)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img", html)

    def test_k_unvalidated_node_id_never_enters_the_action(self):
        # render_page(validate=False) on a hand-built tree: a malformed id falls
        # back to the inert render rather than entering the action URL.
        tree = form_tree({}, FULL_CONTENT, form_id='bad"id')
        html = render_page(tree, lang="en", validate=False, form_action_base=self.BASE)
        self.assertNotIn("<form", html)
        self.assertIn("mz-form-inert", html)


if __name__ == "__main__":
    unittest.main()
