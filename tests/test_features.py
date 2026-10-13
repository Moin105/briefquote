import pytest

from briefquote.features import PROJECT_TYPES, encode_project_type, featurize, load_history, regression_rows


def test_featurize(sample_scope):
    assert featurize(sample_scope) == {
        "project_type": "web",
        "complexity": 4,
        "deliverables_count": 7,
        "integrations_count": 2,
        "has_design_provided": True,
        "has_clear_requirements": True,
    }


def test_encode_project_type_stable():
    assert PROJECT_TYPES[0] == "web"
    assert encode_project_type("web") == 0
    assert encode_project_type("devops") == PROJECT_TYPES.index("devops")


def test_load_history(history_path):
    df = load_history(history_path)
    assert len(df) == 30
    assert len(regression_rows(df)) == (df["outcome"] != "cancelled").sum()


def test_load_history_missing_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("project_type,complexity\nweb,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_history(p)
