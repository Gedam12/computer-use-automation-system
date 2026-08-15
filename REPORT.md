# 1. Architecture

I implemented a small end-to-end computer-use automation system around a local mock banking application. The target represents a back-office application where an operator searches for a member and reads account information.

The architecture deliberately separates discovery from production execution.

During discovery, Gemini 3.5 Flash receives the goal, current visible UI state, and previous actions. It selects one action at a time (`type`, `click`, `read`, or `done`). Playwright executes that action against the live browser, and the resulting state is observed again. This creates an observe → decide → act loop rather than asking the model to generate the entire workflow upfront.

Once the goal succeeds, the actions are converted into a structured capability artifact. The model transcript itself is not required for replay.

Production-style replay loads the artifact, substitutes invocation parameters, validates actions against policy, executes the recorded steps through Playwright, extracts declared outputs, verifies the final checkpoint, and returns a structured result. The LLM is not invoked during replay.

The major architectural boundary is:

    Goal
      ↓
    LLM Discovery
      ↓
    Capability Artifact
      ↓
    Deterministic Replay
      ↓
    Structured Result

I chose Python because it provides straightforward integration among Playwright, Pydantic, and the model SDK. Playwright provides reliable browser automation while still allowing the browser-specific interaction layer to remain separate from the capability model.

The main trade-off is that the implemented surface uses DOM-based browser automation. This is appropriate for the concrete demo but is not sufficient for every legacy application. I therefore isolate surface interaction behind `BrowserSurface` so other implementations can use accessibility trees, screenshots/coordinates, or desktop automation without changing the high-level capability contract.


# 2. Artifact schema

The artifact is a typed Pydantic model serialized as JSON. It contains:

- artifact version
- capability name and description
- target application
- typed input parameters
- typed outputs
- ordered steps
- locator information for each step
- parameterized values
- success checkpoint
- metadata such as surface type and risk level

For example, discovery performed the lookup using member `12345`, but the recorded type action stores `{{member_id}}` rather than the concrete value. The same artifact was then successfully replayed for member `67890`.

Actions and locators are modeled separately. A step describes the semantic operation (`type`, `click`, `read`, or `wait`), while a locator describes how the target control is resolved.

This separation matters for heterogeneous environments. The capability describes what operation is required without requiring every future surface to use the same perception mechanism.

The schema also declares `savings_balance` as a numeric output. Replay normalizes the UI text into a number before returning it, so the runtime result respects the declared contract.

The artifact is versioned and human-readable because I expect discovered artifacts to go through validation/review before being approved for unattended execution.

One issue observed during the real discovery run reinforced this decision: the model initially generated two candidate read steps, one of which selected only the "Savings Balance:" label. The artifact was reviewable, so the redundant locator was identified and removed. In a production system I would automate this validation and introduce artifact lifecycle states such as draft, validated, and approved.


# 3. Determinism & error handling

Replay does not ask an LLM what to do. Given an artifact and invocation inputs, it executes the same ordered actions through the surface adapter.

Parameter substitution converts values such as `{{member_id}}` into the invocation-specific value. After execution, replay verifies the artifact's checkpoint rather than assuming that the preceding click succeeded.

The result contract distinguishes different classes of outcomes.

A successful lookup returns:

    status: success
    outputs:
      savings_balance: <number>

An unknown member returns:

    status: business_outcome
    outcome: member_not_found

This is intentionally not treated as an exception because "member not found" is a legitimate result the calling agent needs to understand.

Policy violations and unexpected browser/runtime exceptions return structured failures with an `error_type` and diagnostic information.

Replay also records step-level execution evidence and captures a screenshot for runtime failures.

The current implementation has limited recoverable-condition support. It includes waiting for page loads, but does not yet implement a generalized retry/backoff taxonomy for transient loads, session expiration, dialogs, or permission screens. I would add explicit condition detectors and bounded recovery policies rather than allowing arbitrary retry behavior.

Locator quality is also treated as part of determinism. The current artifact can use text, role, label/name, CSS, and XPath-compatible Playwright selectors. In production I would store ranked locator alternatives and validation evidence rather than relying on one discovered selector.


# 4. Heterogeneity & multi-tenant

The current implementation targets a web application, but the artifact is intentionally separated from the browser implementation.

`BrowserSurface` is responsible for resolving locators and performing actions. A legacy-web implementation could add accessibility-tree, frame-aware, table-aware, or screenshot/coordinate targeting. A desktop implementation could implement the same conceptual operations through OS accessibility APIs or a desktop automation framework.

The artifact therefore remains the capability contract while the surface adapter determines how controls are perceived and manipulated.

For multi-tenant reuse, I would separate a vendor-level capability from tenant-specific configuration.

A base artifact could represent:

    vendor product + product version + capability

Tenant profiles could then provide:

- entry URL
- branding-specific text aliases
- locator overrides
- enabled/disabled features
- version information
- tenant-specific policy restrictions

Replay would first try the validated base locator set and then permitted tenant/version overrides.

I would detect drift through checkpoint failures, locator-resolution failures, and replay stability metrics. A failing tenant should not automatically mutate the shared base artifact. Instead, the system should collect evidence and route the variant for review or rediscovery.

This allows hundreds of institutions using the same vendor application to share a capability while still supporting controlled specialization where configurations differ.


# 5. Escalation & handoff

Replay can escalate when it reaches a state where it cannot safely verify completion.

For the demonstration, I created an artifact with an intentionally invalid checkpoint. Replay completed the normal browser actions, detected that the expected checkpoint was missing, captured a screenshot, and requested human intervention.

Importantly, Playwright did not close or recreate the browser. Automation paused while the same live browser session remained available.

The terminal displayed the reason for escalation and instructed the operator to interact with the browser. I manually operated that same session and then signaled completion by pressing Enter. Automation resumed and re-evaluated the checkpoint.

The handoff state records:

- whether human control is active
- escalation reason
- request timestamp
- resume timestamp
- operator note

This is deliberately a minimal operator surface. The terminal is acting as the control-transfer interface rather than a production co-browsing console.

A production implementation would route an intervention object containing capability ID, tenant, current step, screenshot/state evidence, and reason to an operator service. It would also record actual operator actions rather than the current generic operator note and enforce an explicit automation/operator ownership lease so both cannot control the session simultaneously.


# 6. Safety

Safety checks are performed independently of the LLM.

The current `SafetyPolicy` contains an explicit target allowlist. Only the local demo application (`127.0.0.1:8000` or `localhost:8000`) is permitted.

The policy also restricts executable action types. Replay validates actions before execution rather than trusting the artifact blindly.

The demo capability is read-only and marked with a `risk_level` in artifact metadata. For a production system I would make risk an enforceable policy concept rather than metadata only.

For example:

- read/navigation actions: automatically allowed within policy
- reversible writes: allowed only for approved capabilities
- financial or irreversible actions: require explicit approval immediately before execution

Secrets are loaded from environment variables. `.env` is excluded from source control, and API keys are not stored in artifacts or evidence.

The demo uses synthetic member data. A production financial environment would additionally require field-level redaction before logging, encrypted evidence storage, retention policies, access controls, audit trails, and strict prevention of raw PII or credentials entering model prompts.


# 7. Cuts

I deliberately implemented a thin vertical slice of every core requirement instead of building production infrastructure.

I did not build:

- a production operator console
- native desktop automation
- screenshot/coordinate-based discovery
- generalized recovery for every runtime condition
- multi-tenant storage or routing infrastructure
- automatic locator fallback ranking
- artifact approval/version-management infrastructure
- distributed workers, queues, or orchestration services

The current handoff uses the terminal as a minimal operator control surface. It proves that automation can pause, preserve the same browser session, transfer control, and resume, but it does not provide real multi-user co-browsing.

The discovery model also receives visible page text rather than a full accessibility tree or screenshot. That was sufficient to demonstrate the required real LLM-driven run while keeping the implementation focused.

With more time, my first improvements would be:

1. Add artifact validation and approval states so raw discovery output cannot immediately become production automation.
2. Add ranked locator strategies and accessibility/screenshot-based surface adapters for legacy applications.
3. Expand the replay result taxonomy with bounded recovery for timeouts, dialogs, permission failures, and session expiry.
4. Capture exact human actions during handoff and implement explicit session ownership.
5. Add tenant/vendor inheritance and replay stability metrics to safely reuse capabilities across institutions.

The goal of this implementation is therefore not to simulate a complete production platform, but to demonstrate the full architectural thread: a real LLM discovers a workflow, that workflow becomes a typed reusable capability, the capability executes deterministically without the model, runtime outcomes are handled deliberately, safety policy constrains execution, and a human can take control of the same live session when automation cannot safely continue.