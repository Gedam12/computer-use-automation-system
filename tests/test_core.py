import pytest

from automation.models import (
    ActionType,
    CapabilityArtifact,
)
from automation.policy import (
    PolicyViolation,
    SafetyPolicy,
)
from automation.replay import (
    normalize_output,
    substitute_parameters,
)


def test_parameter_substitution():
    result = substitute_parameters(
        "{{member_id}}",
        {"member_id": "12345"},
    )

    assert result == "12345"


def test_savings_balance_normalization():
    result = normalize_output(
        "savings_balance",
        "Savings Balance: $ 8920.50",
    )

    assert result == 8920.50
    assert isinstance(result, float)


def test_balance_with_comma():
    result = normalize_output(
        "savings_balance",
        "Savings Balance: $ 15,440.10",
    )

    assert result == 15440.10


def test_invalid_balance_raises_error():
    with pytest.raises(ValueError):
        normalize_output(
            "savings_balance",
            "Savings Balance:",
        )


def test_allowed_target():
    policy = SafetyPolicy()

    policy.validate_target(
        "http://127.0.0.1:8000"
    )


def test_disallowed_target():
    policy = SafetyPolicy()

    with pytest.raises(PolicyViolation):
        policy.validate_target(
            "https://example.com"
        )


def test_allowed_action():
    policy = SafetyPolicy()

    policy.validate_action(
        ActionType.READ
    )


def test_discovered_artifact_is_valid():
    import json

    with open(
        "artifacts/discovered_lookup_savings_balance.json",
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    artifact = CapabilityArtifact.model_validate(data)

    assert artifact.capability_name == "lookup_savings_balance"
    assert len(artifact.steps) == 3
    assert artifact.steps[0].action == ActionType.TYPE
    assert artifact.steps[1].action == ActionType.CLICK
    assert artifact.steps[2].action == ActionType.READ