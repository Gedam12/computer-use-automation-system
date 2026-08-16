# Computer-Use Automation System

A small end-to-end computer-use automation system that demonstrates how an LLM can discover a workflow against a live UI, save it as a reusable capability, and replay it deterministically without the LLM.

The demo uses a local mock banking application to look up a member and return their savings balance.

## How It Works

```text
Natural-language goal
        ↓
LLM Discovery
(observe → decide → act)
        ↓
Typed Capability Artifact
        ↓
Deterministic Replay
(no LLM)
        ↓
Structured Result
```

The system also includes:

- Parameterized inputs and typed outputs
- Business-outcome and failure handling
- Safety allowlists
- Structured run evidence
- Human-in-the-loop handoff using the same live browser session

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
│   ├── handoff_checkpoint_failure.png
│   └──successful_lookup.png
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

## Setup

### Requirements

- Python 3.11+
- Chromium
- Gemini API key

Create and activate a virtual environment:

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

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

Secrets are excluded from source control through `.gitignore`.

## Quick Demo

### 1. Start the target application

Run:

```powershell
uvicorn app.demo_app:app --reload
```

The mock banking application will be available at:

```text
http://127.0.0.1:8000
```

### 2. Run LLM Discovery

Keep the application running.

In another terminal with the virtual environment activated, run:

```powershell
python -c "import asyncio; from automation.discovery import discovery_run; result=asyncio.run(discovery_run('Look up member 12345 and return the current savings balance', 'http://127.0.0.1:8000', {'member_id':'12345'})); print(result)"
```

During discovery, Gemini observes the live UI, chooses one action at a time, and Playwright executes those actions.

A successful discovery creates:

```text
artifacts/discovered_lookup_savings_balance.json
```

Discovery evidence is written to:

```text
evidence/discovery_latest.json
```

### 3. Replay Without the LLM

Replay the discovered capability with a different member ID:

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

Replay uses the saved artifact and deterministic browser actions. Gemini is not used in the replay decision path.

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

`member_not_found` is treated as a valid business outcome rather than a runtime failure.

## Human Handoff

`artifacts/handoff_test.json` contains a deliberately invalid checkpoint used to exercise the escalation path.

Run:

```powershell
python -c "import asyncio; from automation.replay import replay_capability; result=asyncio.run(replay_capability('artifacts/handoff_test.json', {'member_id':'12345'})); print(result)"
```

When replay cannot verify the expected checkpoint:

1. Automation pauses.
2. The same Playwright browser session remains open.
3. A human can manually interact with the live session.
4. The human returns to the terminal and presses Enter.
5. Automation resumes and checks the checkpoint again.

Handoff evidence is captured in:

```text
evidence/handoff_checkpoint_failure.png
```

## Safety

Execution is constrained by `SafetyPolicy`.

- Only the local demo target is allowlisted.
- Only approved action types can execute.
- Secrets are loaded from environment variables.
- API keys are not stored in artifacts or evidence.
- The demo uses synthetic member data.

The production safety model and its limitations are discussed in `REPORT.md`.

## Tests

Run:

```powershell
python -m pytest -v
```

Current test result:

```text
8 passed
```

The tests cover:

- Parameter substitution
- Savings-balance output normalization
- Invalid output handling
- Allowed and blocked targets
- Allowed actions
- Artifact schema validation

## Evidence

The `/evidence/` directory contains:

- `discovery_latest.json` — structured evidence from the real LLM-driven discovery run.
- `replay_latest.json` — structured evidence from deterministic replay.
- `successful_lookup.png` — screenshot captured automatically after a successful replay.
- `handoff_checkpoint_failure.png` — screenshot evidence from the human-handoff scenario.

## Design Details

See [`REPORT.md`](REPORT.md) for the deeper design discussion, including:

- Architecture and trade-offs
- Artifact schema
- Determinism and error handling
- Heterogeneous and legacy surfaces
- Multi-tenant reuse
- Human escalation and control transfer
- Safety
- Deliberate cuts and next steps
