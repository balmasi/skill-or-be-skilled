---
name: co-plan
description: Pressure-tests a plan through a collaborative, one-question-at-a-time decision interview. Use when the user asks to co-plan, challenge a proposal, resolve open choices, or reach shared understanding before acting.
---

# Co-plan

Turn an incomplete plan into a shared, decision-ready plan. Challenge assumptions while leaving ownership with the user.

## Quick start

For requests such as:

- "Co-plan my product launch."
- "Challenge this hiring plan before I commit to it."
- "Help me resolve the open choices in this proposal."

Briefly restate the outcome and constraints, then ask the single highest-leverage unresolved question with a recommended answer and its main trade-off.

## Rules

- Ask exactly one question per turn.
- First inspect files, code, and prior conversation; do not ask what existing evidence answers.
- Ask the highest-leverage or highest-risk unresolved question first; resolve prerequisites before downstream details.
- With each question, include at least one recommended answer, why, and the main trade-off.
- Challenge vague language, hidden assumptions, conflicting requirements, and premature certainty.
- Use concrete scenarios when abstraction stalls.
- During the interview, do not perform planned work unless the user explicitly changes the task.
- Do not create or update project docs.

## Plan state

Track concise:

- **Decisions**: confirmed choices.
- **Assumptions**: unverified beliefs currently treated as true.
- **Open questions**: unresolved choices that materially affect the plan.
- **Risks**: plausible failure modes or accepted trade-offs.

Show state only when it changes materially, the user asks, or it helps resolve a contradiction. Do not repeat the full ledger after every answer.

## Loop

1. Restate the intended outcome and known constraints briefly.
2. Map the decision tree behind the plan.
3. Select the unresolved branch blocking the most other decisions.
4. Ask one focused question covering the decision, recommendation, rationale, and primary trade-off.
5. Wait for the user's answer.
6. Update plan state and reconcile the answer with earlier decisions.
7. Continue until no material branch remains unresolved.

If an answer contradicts prior decisions or constraints, surface it immediately and ask which should win.

## Completion

Finish only when the plan is actionable and both parties share the same understanding. Provide the agreed outcome, confirmed decisions, remaining assumptions and risks, intentionally deferred questions, and next concrete action. Do not claim completion while vague language hides a material decision.
