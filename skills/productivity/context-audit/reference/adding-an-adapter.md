# Adding an agent

Two files: `scripts/adapters/<agent>.py` and `reference/agent-<agent>.md`. Nothing in
`capture.py`, `analyze.py` or `sweep.py` should need to change — if it does, the
abstraction is in the wrong place, so move the seam rather than special-casing.

## 1. The adapter

Subclass `adapters.base.Adapter` and register it in `adapters/__init__.py`.
Three groups of methods:

**drive** — `env`, `command`, `send_prompt`, `wait_ready`, `self_check`,
`disable_tools_args`. `env` must point the agent at `http://127.0.0.1:{port}`
via whatever base-URL variable it honours (`ANTHROPIC_BASE_URL`,
`OPENAI_BASE_URL`, …). `wait_ready` must not return until everything that will
appear in the request has loaded; blind sleeps produce silently wrong numbers,
which is why `self_check` exists as a second line of defence.

**parse** — turn the recorded body into a `Capture(tools, system, messages,
texts)`. `Tool.schema` is handed straight back to the counter, so keep it in the
provider's own shape. `texts` is the list of message text blocks that get priced
individually. `sections()` declares extra breakdowns of a single block (see
Claude's deferred-tool and skills lists): a `match` predicate plus a `split` that
returns `(label, weight, note)` rows whose weights apportion the block's cost.

**price** — return a `Counter`. It needs `count(tools, system, messages)`, and
may override `tool_price` (Claude's caches on disk by schema hash) and `wave`
(to run counts concurrently). A provider without a token-counting endpoint can
tokenise locally instead — the pipeline only needs integers back.

## 2. Things that will bite

- **Solo-pricing a tool includes a fixed per-request tool-block overhead.** The
  generic code already solves it as `OH = (Σdeltas − (all − base)) / (N − 1)`,
  but it needs `tool_price` to return `None` (not raise) for pseudo-tools the
  provider rejects in isolation, so it can fall back to leave-one-out.
- **Return 400 from the capture proxy, never 529.** 529 is retryable, so the CLI
  backs off exponentially and a capture takes minutes instead of seconds. The
  proxy is generic and already does this.
- **Don't predict a saving by subtracting schema costs — it undercounts.** Some
  tools carry context beyond their own schema. Always measure with `sweep.py`.

## 3. The reference page

`reference/agent-<agent>.md` holds the judgment, not the mechanics: which tools are
worth cutting, which are helpful and why, where a denial is written and at
what scope, and how to verify a total against a real run. SKILL.md reads this
file for the chosen agent and stays agent-neutral itself.
