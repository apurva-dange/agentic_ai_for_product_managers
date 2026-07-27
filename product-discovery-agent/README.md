# Product Discovery Agent

**What it solves:** product decisions frequently get made on opinion, the
loudest stakeholder, or a single anecdote, instead of evidence.

**What the agent does:** given a feature question ("Should we build dark
mode?"), it plans what evidence it needs, calls local tools to gather that
evidence one piece at a time, decides whether it has enough, and only then
produces a structured, schema-validated recommendation - never a snap
judgment.

**What the agentic loop demonstrates:** a model deciding *what it doesn't
know yet*, calling a tool to find out, reading the result back into its own
memory, and repeating until it has enough to answer - the core mechanic
behind every real tool-using AI agent, shown here without hiding any of it.

```mermaid
flowchart LR
    Q([Product question]) --> L{Evidence\ncomplete?}
    L -->|no| T[Call a tool] --> R[Read result into history] --> L
    L -->|yes| Rec([Structured recommendation])
```

**One example result:** asking *"Should we build dark mode?"* leads the
agent through customer feedback, usage analytics, competitor research,
effort estimation, and risk checking, and produces:

```json
{
  "feature": "dark mode",
  "recommendation": "Build now",
  "confidence": "High",
  "executive_summary": "For 'dark mode': there is meaningful customer demand; usage analytics offer a related (correlational, not causal) signal; estimated engineering effort is medium; identified risk levels include Low. Based on this evidence, the suggested next step is: build now."
}
```

(Full output: [examples/dark_mode_output.json](examples/dark_mode_output.json))

**How to run the demo:**

```bash
pip install -r requirements.txt
python app.py --scenario dark-mode
```

No API key, database, or network access required.

---

## Table of contents

- [Project overview](#project-overview)
- [Business problem](#business-problem)
- [Solution](#solution)
- [The agentic loop](#the-agentic-loop)
- [Architecture](#architecture)
- [Example workflow: dark mode, start to finish](#example-workflow-dark-mode-start-to-finish)
- [Failure scenarios](#failure-scenarios)
- [Installation](#installation)
- [Usage](#usage)
- [Testing](#testing)
- [Example output](#example-output)
- [Product-management value](#product-management-value)
- [Limitations](#limitations)
- [Future improvements](#future-improvements)
- [Interview talking points](#interview-talking-points)
- [What I learned](#what-i-learned)

## Project overview

The Product Discovery Agent is a local, terminal-based AI agent that helps a
product manager evaluate a feature idea. It is the first project in a
portfolio series about how reliable AI agents are designed - specifically,
it demonstrates that an agent is more than a chatbot: it can reason about
what information it's missing, take actions (tool calls) to get it, observe
the results, and keep going until it has enough evidence to answer
responsibly.

It runs entirely offline on deterministic mock logic and local JSON data, so
the full workflow - including failure handling and edge cases - is
reproducible every single run.

## Business problem

Product managers constantly receive feature requests from customers,
executives, sales, and competitors. Without a consistent process, these get
evaluated on incomplete information or personal opinion, which leads to:

- Building features few users actually need.
- Prioritizing the loudest stakeholder over real customer evidence.
- Ignoring technical complexity until it's too late.
- Missing usability problems that a feature request is actually a symptom of.
- Shipping without any measurable definition of success.

The agent doesn't replace the product manager's judgment - it makes sure
that judgment is exercised on top of organized evidence instead of a blank
page.

## Solution

Given a feature question, the agent:

1. Plans what categories of evidence are relevant (customer demand, usage
   data, competitive landscape, engineering effort, risk/compliance).
2. Calls local tools to gather that evidence, one or two at a time.
3. Reads each tool result back into a structured message history.
4. Re-evaluates what's still missing and decides whether to call another
   tool, retry a failed one, or stop.
5. Produces a structured recommendation with an explicit confidence level,
   assumptions, limitations, next steps, and proposed success metrics -
   never a bare "yes, build it."

## The agentic loop

At the center of the project is one control-flow shape ([src/loop.py](src/loop.py)):

```python
while iteration < max_iterations:
    response = model.respond(message_history)

    if response.stop_reason == "tool_use":
        append_assistant_response_to_history(response)
        execute_requested_tools(response)
        append_tool_results_to_history()
        continue

    if response.stop_reason == "end_turn":
        return final_response

    handle_unknown_stop_reason()
```

Concretely, in this project:

- **Model response** - [src/mock_model.py](src/mock_model.py)'s `MockModel.respond()` looks at
  the current `EvidencePlan` and deterministically decides what to do next.
  No network call, no randomness - the same question always produces the
  same evidence-gathering path.
- **`stop_reason`** - one of `tool_use`, `end_turn`, or an unsupported value
  (used to test safe failure handling).
- **`tool_use`** - the model is missing evidence and requests one or more
  tool calls in a single turn.
- **Tool execution** - [src/agent.py](src/agent.py)'s `_on_tool_use` calls
  the requested tool(s) through the tool router ([src/tools/__init__.py](src/tools/__init__.py)),
  applying a one-retry policy on failure.
- **Tool result** - each execution produces a `ToolResult` (success or
  failure) that gets appended to the message history - *this step is never
  skipped* in normal operation, which is exactly what "Bug mode 1" below
  breaks on purpose to demonstrate why it matters.
- **History update** - [src/history.py](src/history.py) is the single
  append-only source of truth for everything that happened in the run.
- **Continued loop** - if evidence is still outstanding, the loop calls the
  model again with the updated plan; this can happen many times, and can
  also involve two or more tools in a single response (dark mode's first
  iteration always requests customer feedback *and* analytics together).
- **`end_turn`** - only returned once the evidence plan is complete (or
  everything outstanding has permanently failed after a retry); the agent
  then generates the final structured recommendation.

## Architecture

Full details, a Mermaid flowchart, and a Mermaid sequence diagram (showing
two tool calls before the final answer) live in
[docs/architecture.md](docs/architecture.md) / [docs/architecture.mmd](docs/architecture.mmd).
Short version:

```
User → Product Discovery Agent → Evidence Planner → Agentic Loop →
Tool Router → Local Product Tools → Tool Results → Message History →
Continue or Stop Decision → Structured Recommendation
```

## Example workflow: dark mode, start to finish

```bash
python app.py --scenario dark-mode
```

1. Question: *"Should we build dark mode?"*
2. Evidence plan: customer_feedback, product_analytics, competitor_research,
   engineering_effort, risks.
3. Iteration 1: no evidence yet -> calls **customer feedback search** and
   **product analytics lookup** together (two tools, one iteration).
   - Feedback: 42 matching requests, night-shift/enterprise segment
     over-represented, pain point "eye strain."
   - Analytics: 22% of sessions happen at night, with a higher (but
     explicitly correlational, not causal) abandonment rate.
4. Iteration 2: demand and usage evidence established -> calls
   **competitor research**. Two of three tracked (fictional) competitors
   offer dark mode.
5. Iteration 3: -> calls **engineering effort estimator**. Effort: Medium,
   confidence Medium, clearly labeled as a teaching-purpose estimate.
6. Iteration 4: -> calls **risk and compliance checker**. One Low
   accessibility risk, no human approval required.
7. Iteration 5: evidence plan complete -> `end_turn` -> structured
   recommendation: **Build now / High confidence**, with proposed success
   metrics such as "percentage of active users enabling dark mode" and
   "change in evening-session abandonment."

Full recorded output: [examples/dark_mode_output.json](examples/dark_mode_output.json)
and [examples/sample_trace.json](examples/sample_trace.json).

## Failure scenarios

All of these are runnable, not theoretical:

| Scenario | Command | What happens |
|---|---|---|
| Missing tool-result history (**bug mode 1**) | `python app.py --scenario dark-mode --bug-mode skip-tool-history --max-iterations 4` | The tool runs, but its result is deliberately never appended to history or evidence state. The agent re-requests the same tool every iteration, makes no progress, and hits the iteration cap with an "Insufficient evidence" result. |
| Ending the loop too early (**bug mode 2**) | `python app.py --scenario dark-mode --bug-mode end-too-early` | The loop stops after the very first tool call instead of feeding the result back to the model. Only one of five evidence types is ever collected, producing a low-confidence, incomplete recommendation. |
| Unknown stop reason | `python app.py --scenario dark-mode --demo-unknown-stop-reason` | The simulated model returns an unsupported `stop_reason` on iteration 2. The loop halts safely with a clear error instead of crashing or guessing. |
| Tool failure (with recovery) | `python app.py --scenario dark-mode --demo-failure competitor_research` | The first attempt at that tool is forced to fail transiently; the agent records the failure, retries once, and the retry succeeds. |
| Maximum iteration protection | `python app.py --scenario dark-mode --max-iterations 2` | The evidence plan needs five iterations to complete; capping it at 2 forces the loop to stop with `max_iterations_reached` instead of running forever. |
| Insufficient evidence | `python app.py --scenario unknown-feature` | The question doesn't match any feature in the synthetic datasets, so every tool call fails after a retry. The recommendation is `Insufficient evidence` / `Low` confidence. |

## Installation

```bash
git clone <this-repository>
cd product-discovery-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Run one of the five built-in feature scenarios
python app.py --scenario dark-mode
python app.py --scenario mobile-app
python app.py --scenario ai-meeting-summary
python app.py --scenario onboarding
python app.py --scenario export-pdf

# Type your own question
python app.py --interactive

# Print the full structured history trace at the end
python app.py --scenario dark-mode --show-history

# Save the full trace to a JSON file
python app.py --scenario dark-mode --save-trace output/trace.json

# Failure and edge-case demonstrations
python app.py --scenario dark-mode --demo-failure competitor_research
python app.py --scenario dark-mode --demo-unknown-stop-reason
python app.py --scenario dark-mode --max-iterations 2
python app.py --scenario unknown-feature

# Intentional bug modes (educational comparison)
python app.py --scenario dark-mode --bug-mode skip-tool-history
python app.py --scenario dark-mode --bug-mode end-too-early
```

Run `python app.py --help` for the full flag list.

## Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

35 tests across five files cover the loop mechanics, structured history,
all five tools, recommendation schema validation, tool failure/retry
handling, both bug modes, the iteration cap, unknown stop reasons, and a
static scan for accidental secrets or sensitive-data patterns.

## Example output

Shortened terminal trace (full version in
[examples/dark_mode_run.txt](examples/dark_mode_run.txt)):

```
========================================================================
PRODUCT QUESTION: Should we build dark mode?
========================================================================
EVIDENCE PLAN: customer_feedback, product_analytics, competitor_research, engineering_effort, risks
------------------------------------------------------------------------

ITERATION 1/8 | evidence still required: customer_feedback, product_analytics, competitor_research, engineering_effort, risks
  reasoning: No evidence collected yet. The agent will now call customer feedback search and product analytics lookup, since both are independent evidence sources needed before deeper analysis.
  selected tool: customer_feedback_search
  tool output status: OK
  another iteration required: True
  selected tool: product_analytics_lookup
  tool output status: OK
  another iteration required: True

ITERATION 2/8 | evidence still required: competitor_research, engineering_effort, risks
  reasoning: Established so far: customer demand, product usage evidence. Competitor positioning is still unknown ...
  selected tool: competitor_research
  tool output status: OK
...
STOP REASON: end_turn
  Evidence collection complete. Producing the structured recommendation.
```

Structured result (abridged, full version in
[examples/dark_mode_output.json](examples/dark_mode_output.json)):

```json
{
  "feature": "dark mode",
  "recommendation": "Build now",
  "confidence": "High",
  "executive_summary": "For 'dark mode': there is meaningful customer demand; usage analytics offer a related (correlational, not causal) signal; estimated engineering effort is medium; identified risk levels include Low. Based on this evidence, the suggested next step is: build now.",
  "success_metrics": [
    "Percentage of active users who enable dark mode within 30 days (proposed)",
    "Change in evening-session duration after release (proposed)",
    "Change in evening-session abandonment rate after release (proposed)"
  ],
  "human_decision_required": true
}
```

## Product-management value

- **Feature prioritization** - replaces gut-feel scoring with a repeatable,
  explainable evidence-to-recommendation path.
- **Product discovery** - models the "what do I need to know before I
  decide" step that's often skipped under deadline pressure.
- **Customer research** - shows how to aggregate scattered feedback into
  segment-level demand signals instead of anecdotes.
- **Roadmap planning** - the confidence level and `human_decision_required`
  flag make it clear when a recommendation is roadmap-ready versus still
  needing validation.
- **Experiment design** - the proposed success metrics for each feature are
  a starting point for defining what "success" would actually look like.
- **Risk identification** - surfaces accessibility, privacy, security, and
  legal considerations before they become late-stage surprises.

## Limitations

- The default model is **simulated** (deterministic mock logic), not a real
  LLM - it never generates free text or reasons outside the structured
  `EvidencePlan` it's given.
- All customer feedback, analytics, competitor, effort, and risk data is
  **synthetic** and fabricated for teaching purposes; it does not describe
  any real product, company, or customer.
- Engineering effort estimates are **relative and illustrative** (Low /
  Medium / High / Unknown), not real production commitments.
- Recommendations are **decision support, not decision-making** - they do
  not replace a human product manager's judgment, and `human_decision_required`
  is always `true` for that reason.
- A real deployment would require live data integrations, monitoring,
  evaluation datasets, security review, and governance well beyond what a
  local demo needs.

## Future improvements

- Connect the customer feedback tool to a real feedback platform (e.g. a
  support/CRM export) instead of static JSON.
- Connect the analytics tool to a real product analytics warehouse.
- Add human approval checkpoints before a recommendation is considered final.
- Add an evaluation dataset and scoring harness to measure recommendation
  quality over time.
- Add tool-call monitoring/observability (latency, error rates, retry counts).
- Add a real Anthropic API adapter behind an environment variable
  (`ANTHROPIC_API_KEY`, see [.env.example](.env.example)) implementing the
  same `respond(evidence_plan, iteration)` interface as `MockModel`, so the
  loop itself never has to change.
- Add confidence calibration informed by how often past recommendations at
  a given confidence level turned out to be right.
- Add a lightweight web interface on top of the same agent/loop code.

## Interview talking points

1. **The loop is generic; the agent is not.** `loop.py` only knows about
   `stop_reason`, tool execution, and iteration caps - it has no idea what
   a "feature" or "evidence type" is. That separation is what let me test
   the loop mechanics and the domain logic independently.
2. **Message history is the agent's only memory**, and that's demonstrated,
   not just claimed - Bug mode 1 shows what happens when a tool result never
   makes it into history: the agent's evidence state can never advance, so
   it repeats the same request until it hits the iteration cap.
3. **Stopping conditions are as important as continuation logic.** This
   project explicitly handles four distinct ways a run can end
   (`end_turn`, `unknown_stop_reason`, `max_iterations_reached`, and the
   intentional `bug_mode_end_too_early`), because an agent that never stops
   safely is more dangerous than one that stops too early.
4. **Determinism was a deliberate design constraint**, not a limitation I
   settled for. A mock model that reasons over structured evidence state
   (rather than free text) means every scenario in this README is
   reproducible on every run - which made writing tests for edge cases
   (retries, failures, unknown stop reasons) straightforward instead of
   flaky.
5. **The recommendation schema forces honesty about uncertainty.**
   `confidence` and `human_decision_required` aren't decorative - the
   recommendation logic actively caps confidence and blocks strong
   recommendations ("Build now") whenever critical evidence (customer
   demand or engineering effort) is missing.

## What I learned

*(Editable - write your own observations here.)*

- What I learned about tool-use loops:
- Why message history matters:
- Why stopping conditions matter:
- How product requirements affect agent behavior:
- How I would improve this project for production:
