import json
import re
from typing import Any, Dict

from playwright.async_api import async_playwright

from automation.browser import BrowserSurface
from automation.handoff import HumanHandoff
from automation.logging_utils import utc_now, write_json_log
from automation.models import (
    ActionType,
    CapabilityArtifact,
)
from automation.policy import SafetyPolicy, PolicyViolation


def substitute_parameters(value: str, inputs: Dict[str, Any]) -> str:
    result = value

    for key, input_value in inputs.items():
        result = result.replace(
            f"{{{{{key}}}}}",
            str(input_value),
        )

    return result


def normalize_output(output_name: str, value: str) -> Any:
    if output_name == "savings_balance":
        match = re.search(r"[\d,]+\.\d{2}", value)

        if not match:
            raise ValueError(
                f"Could not parse savings balance from: {value}"
            )

        return float(
            match.group(0).replace(",", "")
        )

    return value


async def replay_capability(
    artifact_path: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    with open(artifact_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    artifact = CapabilityArtifact.model_validate(data)

    policy = SafetyPolicy()
    handoff = HumanHandoff()

    run_log = {
        "run_type": "replay",
        "capability": artifact.capability_name,
        "started_at": utc_now(),
        "inputs": inputs,
        "steps": [],
    }

    try:
        policy.validate_target(artifact.target)

    except PolicyViolation as exc:

        result = {
            "status": "failure",
            "error_type": "policy_violation",
            "error": str(exc),
            "outputs": {},
        }

        run_log["result"] = result
        run_log["finished_at"] = utc_now()

        write_json_log(
            "replay_latest.json",
            run_log,
        )

        return result

    outputs: Dict[str, Any] = {}

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        surface = BrowserSurface(page)

        try:

            await page.goto(
                artifact.target,
                wait_until="domcontentloaded",
            )

            for step in artifact.steps:

                policy.validate_action(step.action)

                step_log = {
                    "step_id": step.id,
                    "action": step.action.value,
                    "description": step.description,
                    "started_at": utc_now(),
                }

                if step.action == ActionType.TYPE:

                    value = substitute_parameters(
                        step.value or "",
                        inputs,
                    )

                    await surface.type_text(
                        step.locator,
                        value,
                    )

                    step_log["status"] = "completed"

                elif step.action == ActionType.CLICK:

                    await surface.click(
                        step.locator
                    )

                    await page.wait_for_load_state(
                        "domcontentloaded"
                    )

                    member_not_found = page.get_by_text(
                        "Member not found",
                        exact=True,
                    )

                    if await member_not_found.is_visible():

                        step_log["status"] = "completed"
                        step_log["finished_at"] = utc_now()

                        run_log["steps"].append(step_log)

                        result = {
                            "status": "business_outcome",
                            "outcome": "member_not_found",
                            "message": "Member not found",
                            "outputs": {},
                        }

                        run_log["result"] = result
                        run_log["finished_at"] = utc_now()

                        write_json_log(
                            "replay_latest.json",
                            run_log,
                        )

                        return result

                    step_log["status"] = "completed"

                elif step.action == ActionType.READ:

                    text = await surface.read_text(
                        step.locator
                    )

                    if step.output_name:
                        outputs[step.output_name] = normalize_output(
                            step.output_name,
                            text,
                        )

                    step_log["status"] = "completed"

                elif step.action == ActionType.WAIT:

                    await page.wait_for_timeout(1000)

                    step_log["status"] = "completed"

                step_log["finished_at"] = utc_now()

                run_log["steps"].append(step_log)

            checkpoint_visible = await surface.is_visible(
                artifact.checkpoint.locator
            )

            if not checkpoint_visible:

                screenshot_path = (
                    "evidence/handoff_checkpoint_failure.png"
                )

                await page.screenshot(
                    path=screenshot_path,
                    full_page=True,
                )

                run_log["handoff_requested"] = {
                    "reason": "checkpoint_not_reached",
                    "screenshot": screenshot_path,
                    "timestamp": utc_now(),
                }

                await handoff.request(
                    "Expected success checkpoint was not reached."
                )

                run_log["handoff"] = handoff.to_dict()

                checkpoint_visible = await surface.is_visible(
                    artifact.checkpoint.locator
                )

                if not checkpoint_visible:

                    result = {
                        "status": "failure",
                        "error_type": "checkpoint_not_reached",
                        "error": (
                            "Checkpoint was still not visible "
                            "after human intervention."
                        ),
                        "outputs": outputs,
                    }

                    run_log["result"] = result
                    run_log["finished_at"] = utc_now()

                    write_json_log(
                        "replay_latest.json",
                        run_log,
                    )

                    return result

            # Capture evidence of a successful replay
            success_screenshot_path = (
                "evidence/successful_lookup.png"
            )

            await page.screenshot(
                path=success_screenshot_path,
                full_page=True,
            )

            result = {
                "status": "success",
                "capability": artifact.capability_name,
                "outputs": outputs,
            }

            run_log["result"] = result
            run_log["success_screenshot"] = (
                success_screenshot_path
            )
            run_log["finished_at"] = utc_now()

            if handoff.state.requested_at:
                run_log["handoff"] = handoff.to_dict()

            write_json_log(
                "replay_latest.json",
                run_log,
            )

            return result

        except PolicyViolation as exc:

            result = {
                "status": "failure",
                "error_type": "policy_violation",
                "error": str(exc),
                "outputs": outputs,
            }

            run_log["result"] = result
            run_log["finished_at"] = utc_now()

            write_json_log(
                "replay_latest.json",
                run_log,
            )

            return result

        except Exception as exc:

            screenshot_path = "evidence/replay_failure.png"

            try:
                await page.screenshot(
                    path=screenshot_path,
                    full_page=True,
                )
            except Exception:
                screenshot_path = None

            result = {
                "status": "failure",
                "error_type": "runtime_error",
                "error": str(exc),
                "outputs": outputs,
            }

            run_log["result"] = result
            run_log["failure_screenshot"] = screenshot_path
            run_log["finished_at"] = utc_now()

            write_json_log(
                "replay_latest.json",
                run_log,
            )

            return result

        finally:
            await browser.close()