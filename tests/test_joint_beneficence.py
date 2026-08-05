"""Joint beneficence — real rules, no mocks."""
import pytest

from nex.mission import PartyEffect, evaluate_joint_beneficence


def test_strict_all_advanced_passes():
    r = evaluate_joint_beneficence(
        human="advanced",
        ai_partner="advanced",
        shared_or_third="advanced",
        mode="strict",
    )
    assert r.ok is True
    assert "PASS" in r.summary


def test_any_harm_fails():
    r = evaluate_joint_beneficence(
        human="advanced",
        ai_partner="neutral",
        shared_or_third="harmed",
        mode="default",
    )
    assert r.ok is False
    assert r.shared_or_third == PartyEffect.HARMED


def test_default_allows_ai_neutral_assist():
    r = evaluate_joint_beneficence(
        human="advanced",
        ai_partner="neutral",
        shared_or_third="advanced",
        mode="default",
    )
    assert r.ok is True


def test_default_rejects_human_neutral_only():
    r = evaluate_joint_beneficence(
        human="neutral",
        ai_partner="advanced",
        shared_or_third="advanced",
        mode="default",
    )
    assert r.ok is False


def test_ego_only_human_without_shared_fails():
    r = evaluate_joint_beneficence(
        human="advanced",
        ai_partner="advanced",
        shared_or_third="neutral",
        mode="default",
    )
    assert r.ok is False


def test_invalid_effect_raises():
    with pytest.raises(ValueError):
        evaluate_joint_beneficence(
            human="win",
            ai_partner="advanced",
            shared_or_third="advanced",
        )
