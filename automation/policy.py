from urllib.parse import urlparse

from automation.models import ActionType


class PolicyViolation(Exception):
    pass


class SafetyPolicy:
    def __init__(self):
        self.allowed_hosts = {
            "127.0.0.1:8000",
            "localhost:8000",
        }

        self.allowed_actions = {
            ActionType.TYPE,
            ActionType.CLICK,
            ActionType.READ,
            ActionType.WAIT,
        }

    def validate_target(self, target: str) -> None:
        parsed = urlparse(target)

        if parsed.netloc not in self.allowed_hosts:
            raise PolicyViolation(
                f"Target is not allowlisted: {parsed.netloc}"
            )

    def validate_action(self, action: ActionType) -> None:
        if action not in self.allowed_actions:
            raise PolicyViolation(
                f"Action is not allowed: {action}"
            )