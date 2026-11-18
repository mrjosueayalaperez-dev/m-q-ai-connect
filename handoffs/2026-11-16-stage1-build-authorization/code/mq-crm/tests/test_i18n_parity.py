from app.i18n import SUPPORTED_LANGUAGES, TEMPLATES, UI


def test_ui_parity_all_languages():
    langs = list(UI.keys())
    assert set(langs) == set(SUPPORTED_LANGUAGES)
    reference = set(UI["en"].keys())
    for lang in langs:
        assert set(UI[lang].keys()) == reference, f"UI keys diverge in {lang}"


def test_every_template_in_every_language():
    for key, tpl in TEMPLATES.items():
        for lang in SUPPORTED_LANGUAGES:
            assert tpl.get(lang), f"template {key} missing language {lang}"
