"""
Unit tests for the TEMPLATES list.
"""
from templatelist import TEMPLATES


def test_templates_is_list():
    """
    GIVEN the TEMPLATES constant from templatelist.py
    WHEN it is imported
    THEN check that it is a list
    """
    assert isinstance(TEMPLATES, list)


def test_templates_not_empty():
    """
    GIVEN the TEMPLATES constant
    WHEN it is checked for content
    THEN check that it contains at least one template name
    """
    assert len(TEMPLATES) > 0


def test_templates_all_strings():
    """
    GIVEN the TEMPLATES constant
    WHEN each entry is inspected
    THEN check that every entry is a string
    """
    for template in TEMPLATES:
        assert isinstance(template, str), f"Expected str, got {type(template)}: {template}"


def test_templates_no_duplicates():
    """
    GIVEN the TEMPLATES constant
    WHEN checked for duplicates
    THEN ensure all entries are unique
    """
    assert len(TEMPLATES) == len(set(TEMPLATES)), "TEMPLATES list contains duplicates"


def test_known_templates_present():
    """
    GIVEN the TEMPLATES constant
    WHEN key non-free templates are checked
    THEN verify they exist in the list
    """
    expected_templates = [
        "Non-free logo",
        "Non-free fair use",
        "Non-free book cover",
        "Non-free album cover",
        "Non-free film screenshot",
    ]
    for name in expected_templates:
        assert name in TEMPLATES, f"Expected template '{name}' not found in TEMPLATES"
