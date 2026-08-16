# Computer-Use Automation System

A small end-to-end computer-use automation system that demonstrates:

* LLM-driven discovery against a live UI
* typed, versioned capability artifacts
* deterministic replay without an LLM
* parameterized inputs and typed outputs
* business-outcome handling
* configurable safety guardrails
* structured run evidence
* human-in-the-loop escalation using the same live browser session

The demo target is a local mock banking back-office application used to look up a member and return their savings balance.

## Architecture Overview

The project separates discovery from production execution.

During discovery, Gemini observes the current UI state, chooses one action at a time, and interacts with the application through Playwright.

A successful discovery run is converted into a typed capability artifact.

That artifact can later be replayed deterministically with different input parameters without invoking the LLM.

High-level flow:

```text
Natural-language goal
        |
        v
LLM discovery loop
Observe -> Decide -> Act
        |
        v
Capability artifact
        |
        v
Deterministic replay
        |
        v
Structured result
```

## Project Structure

```text
interface-ai-assignment/
├── app/
│   └── demo_app.py
│
├── automation/
│   ├── browser.py
│   ├── discovery.py
│   ├── handoff.py
│   ├── logging_utils.py
│   ├── models.py
│   ├── policy.py
│   └── replay.py
│
├── artifacts/
│   ├── discovered_lookup_savings_balance.json
│   └── handoff_test.json
│
├── evidence/
│   ├── discovery_latest.json
│   ├── replay_latest.json
│   └── handoff_checkpoint_failure.png
│
├── tests/
│   └── test_core.py
│
├── .env.example
├── .gitignore
├── README.md
├── REPORT.md
└── requirements.txt
```

## Requirements

* Python 3.11+
* Chromium
* Gemini API key

The implementation was developed using Python and Playwright.

## Setup

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Install Chromium for Playwright:

```powershell
playwright install chromium
```

## Environment Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

Do not commit `.env` or API keys to source control.

A `.env.example` file is included as a reference.

## Start the Demo Application

Run:

```powershell
uvicorn app.demo_app:app --reload
```

The mock banking application will be available at:

```text
http://127.0.0.1:8000
```

Known sample members:

```text
12345
67890
```

An unknown member ID such as:

```text
99999
```

produces a legitimate `member_not_found` business outcome.

## Run LLM Discovery

Keep the demo application running.

In another terminal with the virtual environment activated, run:

```powershell
python -c "import asyncio; from automation.discovery import discovery_run; result=asyncio.run(discovery_run('Look up member 12345 and return the current savings balance', 'http://127.0.0.1:8000', {'member_id':'12345'})); print(result)"
```

The discovery process:

1. Opens the live application.
2. Observes the current UI state.
3. Sends the visible state and goal to Gemini.
4. Executes one model-selected action at a time.
5. Explicitly extracts the requested output.
6. Records successful actions as a reusable artifact.

A successful run creates:

```text
artifacts/discovered_lookup_savings_balance.json
```

and evidence at:

```text
evidence/discovery_latest.json
```

## Run Deterministic Replay

The generated artifact can be replayed with a different member ID without calling Gemini.

For example:

```powershell
python -c "import asyncio; from automation.replay import replay_capability; result=asyncio.run(replay_capability('artifacts/discovered_lookup_savings_balance.json', {'member_id':'67890'})); print(result)"
```

Expected result:

```python
{
    'status': 'success',
    'capability': 'lookup_savings_balance',
    'outputs': {
        'savings_balance': 15440.1
    }
}
```

The replay path uses only the recorded artifact and deterministic browser actions.

## Business Outcome Example

Replay with an unknown member:

```powershell
python -c "import asyncio; from automation.replay import replay_capability; result=asyncio.run(replay_capability('artifacts/discovered_lookup_savings_balance.json', {'member_id':'99999'})); print(result)"
```

Expected result:

```python
{
    'status': 'business_outcome',
    'outcome': 'member_not_found',
    'message': 'Member not found',
    'outputs': {}
}
```

This is treated as a valid business result rather than a runtime crash.

## Human Handoff Demo

The file:

```text
artifacts/handoff_test.json
```

contains a deliberately invalid success checkpoint in order to demonstrate escalation.

Run:

```powershell
python -c "import asyncio; from automation.replay import replay_capability; result=asyncio.run(replay_capability('artifacts/handoff_test.json', {'member_id':'12345'})); print(result)"
```

Replay performs the normal workflow and then detects that the expected checkpoint cannot be reached.

The automation pauses and prints:

```text
=== HUMAN INTERVENTION REQUIRED ===
```

The Playwright browser remains open so a human can manually operate the same live session.

After manual intervention, return to the terminal and press Enter.

The automation resumes, re-checks the checkpoint, records the handoff, and returns a structured result.

## Safety

The replay and discovery paths use an explicit `SafetyPolicy`.

Currently allowed targets:

```text
127.0.0.1:8000
localhost:8000
```

Allowed action classes include:

```text
type
click
read
wait
```

A non-allowlisted target produces a `policy_violation` instead of being executed.

Secrets are loaded from environment variables and are not written into artifacts or logs.

## Evidence

The `evidence/` directory includes:

```text
discovery_latest.json
```

Structured evidence of the real LLM discovery run.

```text
replay_latest.json
```

Structured evidence of deterministic replay, including each executed step and final result.

```text
handoff_checkpoint_failure.png
```

Screenshot captured when the replay reached the deliberately invalid checkpoint used for the human-handoff demonstration.

## Tests

Run:

```powershell
python -m pytest -v
```

The current test suite covers:

* parameter substitution
* typed savings-balance normalization
* comma-formatted balance parsing
* invalid balance handling
* allowed target validation
* blocked target validation
* allowed action validation
* artifact schema validation

Current result:

```text
8 passed
```

## Notes

The implementation intentionally focuses on a small end-to-end vertical slice rather than production-scale infrastructure.

The local banking application is a stand-in for a legacy financial application that does not expose an API.

The browser interaction layer is separated from the capability schema so additional surface implementations, such as accessibility-based browser control or desktop automation, could be added without changing the high-level capability contract.
