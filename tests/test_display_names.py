from src import config, explain


def test_every_category_has_a_display_name():
    for cat in config.ENABLED_CATEGORIES:
        name = explain.category_display(cat)
        assert name and name != cat, f"category {cat} missing display_name"


def test_display_names_unique():
    names = [explain.category_display(c) for c in config.ENABLED_CATEGORIES]
    assert len(set(names)) == len(names), f"duplicate display names: {names}"


def test_display_names_include_required_examples():
    # a smoke check against the Prompt-4 spec table
    expected = {
        "F": "Undefined Terms",
        "B": "Vague Qualifiers",
        "I": "Unnamed References",
        "A": "Word-Level Ambiguity",
        "E": "Unclear Pronouns",
        "G": "Priority Conflicts",
        "H": "Numerical Inconsistencies",
        "J": "Incomplete Specifications",
    }
    for code, name in expected.items():
        assert explain.category_display(code) == name


def test_verdict_display_covers_new_and_legacy():
    assert explain.verdict_display("CONFIRMED_AMBIGUOUS") == "Confirmed Ambiguous"
    assert explain.verdict_display("RESOLVED_BY_CONTEXT") == "Resolved by Context"
    assert explain.verdict_display("PARTIALLY_RESOLVED") == "Partially Resolved"
    assert explain.verdict_display("RESOLVED") == "Resolved by Context"
    assert explain.verdict_display("UNRESOLVED") == "Confirmed Ambiguous"
