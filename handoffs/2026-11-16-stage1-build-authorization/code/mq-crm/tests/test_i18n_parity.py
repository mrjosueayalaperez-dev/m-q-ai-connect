from app.i18n import TEMPLATES, UI


def test_ui_parity_en_es():
    assert set(UI["en"].keys()) == set(UI["es"].keys())


def test_every_template_bilingual():
    for key, tpl in TEMPLATES.items():
        assert tpl["en"] and tpl["es"], f"template {key} missing a language"
