"""Unit tests for deletion alignment helper in plan execution."""

from app.api.plan_execution import _deletion_alignment, _has_deletion_mismatch


def test_deletion_alignment_matches_plan():
    result = _deletion_alignment(
        removed_codes=["CAMTESTBRP", "CAMTESTPRM"],
        planned_deletions=["camtestbrp", "CAMTESTPRM"],
    )

    assert result["planned_deletions"] == ["CAMTESTBRP", "CAMTESTPRM"]
    assert result["unexpected_removed"] == []
    assert result["missing_planned"] == []


def test_deletion_alignment_detects_unexpected_removed():
    result = _deletion_alignment(
        removed_codes=["CAMTESTBRP", "CAMTESTOWM"],
        planned_deletions=["CAMTESTBRP"],
    )

    assert result["planned_deletions"] == ["CAMTESTBRP"]
    assert result["unexpected_removed"] == ["CAMTESTOWM"]
    assert result["missing_planned"] == []


def test_deletion_alignment_detects_missing_planned():
    result = _deletion_alignment(
        removed_codes=["CAMTESTBRP"],
        planned_deletions=["CAMTESTBRP", "CAMTESTOWM"],
    )

    assert result["planned_deletions"] == ["CAMTESTBRP", "CAMTESTOWM"]
    assert result["unexpected_removed"] == []
    assert result["missing_planned"] == ["CAMTESTOWM"]


def test_has_deletion_mismatch_false_when_aligned():
    alignment = _deletion_alignment(
        removed_codes=["CAMTESTBRP"],
        planned_deletions=["CAMTESTBRP"],
    )
    assert _has_deletion_mismatch(alignment) is False


def test_has_deletion_mismatch_true_when_divergent():
    alignment = _deletion_alignment(
        removed_codes=["CAMTESTBRP"],
        planned_deletions=["CAMTESTOWM"],
    )
    assert _has_deletion_mismatch(alignment) is True
