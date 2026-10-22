# PHANTOM Capability Blueprint: Public Patterns from Claude, ChatGPT/OpenAI, and Gemini

**Purpose:** Use publicly documented engineering patterns to build a stronger local assistant around Qwen3-8B. This is not a claim to reverse-engineer proprietary model weights, private prompts, hidden reasoning, or internal service implementations.

## Executive summary

A capable assistant is not only a model. It is a system made from:
- a model that interprets the request and generates a response or tool request;
- application-controlled workflow/orchestration;
- narrow, validated tools for actions and exact computation;
- explicit instructions and safety guardrails;
- short-term conversation state and optionally user-approved local memory;
- verification and evaluation that identify failures.

The model weights are not being retrained by these components. They provide stronger scaffolding around the existing local model, and measurable tests tell us whether that scaffolding helps.

## Publicly documented patterns

### Anthropic / Claude

The public Claude materials document extended thinking for complex problem-solving and planning, and agent workflow patterns such as prompt chaining, routing, parallelization, orchestrator-workers, and evaluator-optimizer. The useful design lesson for PHANTOM is to break difficult tasks into bounded phases, inspect intermediate results, and add a review step only when the task warrants it.

Sources:
- [Claude: extended thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)
- [Anthropic: Building Effective AI Agents](https://resources.anthropic.com/building-effective-ai-agents)
- [Anthropic Claude Cookbooks: agent patterns](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents)

### OpenAI / ChatGPT platform

Public OpenAI agent documentation describes systems built from instructions, tools, guardrails, sessions/context, orchestration, and traces/evaluations. Function calling separates the model's decision to request a tool from the application's responsibility to validate and execute that tool. Traces and graders help diagnose which stage failed.

The useful design lesson for PHANTOM is to keep control flow in the application: validate a proposed tool call, execute only a known function, return its result, and record a redacted trace. Do not allow the model to execute arbitrary shell commands or unrestricted code.

Sources:
- [OpenAI: Building agents](https://developers.openai.com/tracks/building-agents)
- [OpenAI: Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI: Orchestration and handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration)
- [OpenAI: Agent evaluation and trace grading](https://developers.openai.com/api/docs/guides/agent-evals)

### Google Gemini

Public Gemini documentation explains thinking controls and function calling. A function call is a structured request from the model; the application executes the requested function and sends the result back. Gemini's documented tools also demonstrate an important principle: use code/computation or retrieval tools for tasks where those capabilities are more reliable than free-form generation.

The useful design lesson for PHANTOM is to define narrow typed tool contracts, validate tool arguments, execute in the application, then let the model compose the result for the user.

Sources:
- [Gemini: thinking](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini: function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini: tools](https://ai.google.dev/gemini-api/docs/tools)

## PHANTOM's synthesized architecture

1. **Understand** — identify the user's goal, requested format, constraints, and missing information.
2. **Route** — choose direct response, deterministic computation, local retrieval, memory, or a multi-step plan.
3. **Plan lightly** — for multi-step work, state a concise plan internally in structured form; do not over-plan simple conversation.
4. **Act through tools** — only registered functions; validate all arguments; return structured results.
5. **Observe** — inspect tool outputs, errors, and whether the intended subtask was actually completed.
6. **Verify** — re-check calculations, required constraints, source consistency, and unsupported assumptions. Prefer Python for exact arithmetic.
7. **Recover** — if a tool fails, retry only when safe and useful; otherwise explain the blocker and ask a focused question.
8. **Respond** — give a concise answer in the user's language, summarize meaningful actions, distinguish verified facts from estimates.
9. **Trace and evaluate** — log tool names, timings, statuses, and test IDs locally. Never publish personal prompts or full generations by default.
10. **Improve using evidence** — add a regression test for a real failure before changing prompts or rules.

## What PHANTOM will not pretend to copy

- Exact internal model architectures, private system prompts, model weights, or proprietary hidden reasoning from Claude, ChatGPT, or Gemini.
- Their frontier model capabilities by adding prompts alone.
- A successful keyword match as proof that reasoning is correct.
- A tool action as completed unless the local function actually returned success.

## Implementation sequence

- **Phase A — Local core:** LM Studio client, bounded tool loop, Python calculator, local clock, safe project-file reading, and explicitly requested local memory.
- **Phase B — Reliability:** tool-call validation, limits, error recovery, redacted traces, evaluator tests.
- **Phase C — Capability benchmarks:** planning, logic, calculations, context retention, tool use, ambiguity handling, refusal to invent inaccessible facts.
- **Phase D — Learning from failures:** compare runs only when model, prompt, evaluator, and benchmark versions match; preserve old results.
- **Phase E — Optional fine-tuning:** consider only after accumulating consented, curated examples and a reproducible evaluation set. Fine-tuning is not needed for the initial system.

## Local-first and safety constraints

- Model requests go only to the loopback LM Studio endpoint.
- No arbitrary shell execution.
- File-reading tools are confined to the PHANTOM workspace and block likely secret/config files.
- Persistent memory is local, opt-in, and git-ignored.
- Tool calls and experiment results are not uploaded automatically.
- User-visible actions require application-level authorization and actual result checks.
