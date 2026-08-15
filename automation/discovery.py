import json
from typing import Any, Dict, List

from dotenv import load_dotenv
from google import genai
from playwright.async_api import async_playwright

from automation.browser import BrowserSurface
from automation.logging_utils import utc_now, write_json_log
from automation.models import (
    ActionType,
    CapabilityArtifact,
    Checkpoint,
    InputParameter,
    Locator,
    LocatorStrategy,
    OutputField,
    OutputType,
    ParameterType,
    Step,
)
from automation.policy import SafetyPolicy


load_dotenv()


async def collect_page_text(page) -> str:
    body_text = await page.locator("body").inner_text()
    return body_text[:6000]


def build_prompt(
    goal: str,
    page_text: str,
    history: List[Dict[str, Any]],
    outputs: Dict[str, Any],
) -> str:
    return f"""
You are controlling a web application.

Goal:
{goal}

Current visible page text:
{page_text}

Previous actions:
{json.dumps(history, indent=2)}

Outputs already extracted:
{json.dumps(outputs, indent=2)}

You must explicitly extract the requested savings balance before declaring the goal complete.

Choose exactly ONE next action.

Allowed actions:
1. type
2. click
3. read
4. done

Rules:

- Use "done" ONLY after savings_balance has been explicitly extracted with a "read" action.
- Seeing the value in page text is NOT enough.
- Do not invent elements that are not visible.
- Prefer stable visible text or simple CSS selectors.
- Take only one action at a time.
- The savings balance element uses a visible value on the Member Details screen.
- When reading the savings balance, use output_name "savings_balance".

Return ONLY valid JSON.

For type:
{{
  "action": "type",
  "strategy": "css",
  "target": "CSS_SELECTOR",
  "value": "TEXT_TO_TYPE",
  "description": "reason"
}}

For click:
{{
  "action": "click",
  "strategy": "text",
  "target": "VISIBLE_TEXT",
  "description": "reason"
}}

For read:
{{
  "action": "read",
  "strategy": "css",
  "target": "CSS_SELECTOR",
  "output_name": "savings_balance",
  "description": "reason"
}}

When the goal is complete:
{{
  "action": "done",
  "description": "goal completed"
}}
"""


def clean_json_response(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):]

    if text.startswith("```"):
        text = text[len("```"):]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


async def discovery_run(
    goal: str,
    target: str,
    inputs: Dict[str, Any],
    max_steps: int = 8,
) -> Dict[str, Any]:

    policy = SafetyPolicy()
    policy.validate_target(target)

    client = genai.Client()

    history: List[Dict[str, Any]] = []
    recorded_steps: List[Step] = []
    outputs: Dict[str, Any] = {}

    run_log = {
        "run_type": "discovery",
        "goal": goal,
        "target": target,
        "started_at": utc_now(),
        "inputs": inputs,
        "steps": [],
    }

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        surface = BrowserSurface(page)

        try:
            await page.goto(
                target,
                wait_until="domcontentloaded",
            )

            for step_number in range(1, max_steps + 1):

                page_text = await collect_page_text(page)

                prompt = build_prompt(
                    goal=goal,
                    page_text=page_text,
                    history=history,
                    outputs=outputs,
                )

                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                )

                raw_text = response.text or ""
                cleaned = clean_json_response(raw_text)
                decision = json.loads(cleaned)

                action = decision["action"]

                decision_log = {
                    "step_number": step_number,
                    "observed_url": page.url,
                    "decision": decision,
                    "timestamp": utc_now(),
                }

                run_log["steps"].append(decision_log)

                if action == "done":

                    if "savings_balance" not in outputs:
                        history.append(
                            {
                                "action": "system_feedback",
                                "message": (
                                    "Goal is not complete. "
                                    "You must explicitly read savings_balance first."
                                ),
                            }
                        )
                        continue

                    result = {
                        "status": "success",
                        "message": "Discovery goal completed.",
                        "outputs": outputs,
                    }

                    run_log["result"] = result
                    run_log["finished_at"] = utc_now()

                    write_json_log(
                        "discovery_latest.json",
                        run_log,
                    )

                    artifact = CapabilityArtifact(
                        artifact_version="1.0",
                        capability_name="lookup_savings_balance",
                        description=goal,
                        target=target,
                        inputs=[
                            InputParameter(
                                name="member_id",
                                type=ParameterType.STRING,
                                required=True,
                                description="Member ID to look up.",
                            )
                        ],
                        outputs=[
                            OutputField(
                                name="savings_balance",
                                type=OutputType.NUMBER,
                                description=(
                                    "Savings balance returned by the application."
                                ),
                            )
                        ],
                        steps=recorded_steps,
                        checkpoint=Checkpoint(
                            locator=Locator(
                                strategy=LocatorStrategy.TEXT,
                                value="Member Details",
                            ),
                            expected_text="Member Details",
                            description=(
                                "Member details page is visible."
                            ),
                        ),
                        metadata={
                            "surface": "web",
                            "discovered_by": "gemini-3.5-flash",
                            "risk_level": "read_only",
                        },
                    )

                    with open(
                        "artifacts/discovered_lookup_savings_balance.json",
                        "w",
                        encoding="utf-8",
                    ) as file:
                        json.dump(
                            artifact.model_dump(mode="json"),
                            file,
                            indent=2,
                        )

                    return {
                        "status": "success",
                        "artifact_path": (
                            "artifacts/"
                            "discovered_lookup_savings_balance.json"
                        ),
                        "outputs": outputs,
                    }

                if action == "type":

                    target_value = decision["target"]
                    value = decision["value"]

                    locator = Locator(
                        strategy=LocatorStrategy.CSS,
                        value=target_value,
                    )

                    policy.validate_action(ActionType.TYPE)

                    await surface.type_text(
                        locator,
                        value,
                    )

                    recorded_value = value

                    for key, input_value in inputs.items():
                        if str(input_value) == value:
                            recorded_value = f"{{{{{key}}}}}"

                    recorded_steps.append(
                        Step(
                            id=f"step_{len(recorded_steps) + 1}",
                            action=ActionType.TYPE,
                            locator=locator,
                            value=recorded_value,
                            description=decision.get("description"),
                        )
                    )

                elif action == "click":

                    locator = Locator(
                        strategy=LocatorStrategy.TEXT,
                        value=decision["target"],
                    )

                    policy.validate_action(ActionType.CLICK)

                    await surface.click(locator)

                    await page.wait_for_load_state(
                        "domcontentloaded"
                    )

                    recorded_steps.append(
                        Step(
                            id=f"step_{len(recorded_steps) + 1}",
                            action=ActionType.CLICK,
                            locator=locator,
                            description=decision.get("description"),
                        )
                    )

                elif action == "read":

                    locator = Locator(
                        strategy=LocatorStrategy.CSS,
                        value=decision["target"],
                    )

                    policy.validate_action(ActionType.READ)

                    text = await surface.read_text(locator)

                    output_name = decision.get(
                        "output_name",
                        "output",
                    )

                    outputs[output_name] = text

                    recorded_steps.append(
                        Step(
                            id=f"step_{len(recorded_steps) + 1}",
                            action=ActionType.READ,
                            locator=locator,
                            output_name=output_name,
                            description=decision.get("description"),
                        )
                    )

                else:
                    raise ValueError(
                        f"Unsupported model action: {action}"
                    )

                history.append(decision)

            result = {
                "status": "failure",
                "error_type": "max_steps_exceeded",
                "message": (
                    "Discovery did not complete within the step limit."
                ),
            }

            run_log["result"] = result
            run_log["finished_at"] = utc_now()

            write_json_log(
                "discovery_latest.json",
                run_log,
            )

            return result

        except Exception as exc:

            screenshot_path = "evidence/discovery_failure.png"

            try:
                await page.screenshot(
                    path=screenshot_path,
                    full_page=True,
                )
            except Exception:
                screenshot_path = None

            result = {
                "status": "failure",
                "error_type": "discovery_error",
                "error": str(exc),
            }

            run_log["result"] = result
            run_log["failure_screenshot"] = screenshot_path
            run_log["finished_at"] = utc_now()

            write_json_log(
                "discovery_latest.json",
                run_log,
            )

            return result

        finally:
            await browser.close()