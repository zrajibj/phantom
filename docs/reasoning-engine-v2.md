# PHANTOM Reasoning Engine v2

**Status:** First-pass local agent scaffold implemented; actual live-model behavior still needs a local LM Studio run.  
**Target:** Qwen3-8B through the existing LM Studio endpoint.  
**Design goal:** Improve task completion through orchestration and verifiable tools, not just a longer system prompt.

## 1. Design lessons from public agent systems

Claude, ChatGPT/OpenAI, and Gemini publicly document similar high-level building blocks: task decomposition, tool/function calling, application-controlled execution, context, guardrails, and evaluation. PHANTOM borrows these public engineering patterns. It does not reconstruct proprietary model internals or copy hidden prompts.

Sources:
- [Anthropic — Building Effective AI Agents](https://resources.anthropic.com/building-effective-ai-agents)
- [Anthropic — Claude Cookbooks: agent patterns](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents)
- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Agent evaluation](https://developers.openai.com/api/docs/guides/agent-evals)
- [Gemini — Function calling](https://ai.google.dev/gemini-api/docs/function-calling)

## 2. Runtime control loop

PHANTOM uses this task-completion loop:

1. **Understand:** Identify the desired end state, output format, and hard constraints.
2. **Route:** Answer directly for simple conversation; use an approved tool for exact computation, local time, safe project-file retrieval, or explicit memory operations.
3. **Plan:** For multi-step tasks, determine ordered actions, dependencies, and acceptance conditions. Do not expose hidden chain-of-thought; communicate only a concise plan/rationale where useful.
4. **Act:** Qwen may request only registered functions. Python validates the request and dispatches only the named allow-listed tool.
5. **Observe:** Return structured tool results to Qwen, including errors rather than pretending execution succeeded.
6. **Verify:** Cross-check required conditions and use deterministic tools for math. A tool's successful return is evidence of a call, not proof the overall task is complete.
7. **Recover or stop:** Retry only when safe and useful. Tool rounds and calls are bounded. Explain a blocker instead of looping indefinitely.
8. **Respond:** Give a direct answer in the requested language and format, distinguish known facts from assumptions, and say what remains unverified.

## 3. Currently implemented tools and controls

| Capability | Implementation | Boundary |
|---|---|---|
| Exact arithmetic | Restricted Python AST calculator | Numbers and basic arithmetic operators only; no dynamic code evaluation |
| Local time | Reads the computer's local clock | Does not infer remote/current facts |
| Workspace search | Searches selected safe text/code/config-example formats | Resolves and rejects symlinks that leave workspace; skips private/config/output directories |
| Workspace read | Reads a single workspace-relative file | Blocks path traversal and known private config, secret, memory and run-output files |
| Explicit local memory | Local JSON store | Current user message must explicitly request saving; value must appear in that message; likely credentials are refused |
| Trace metadata | Local JSONL trace | Records tool name, status and duration only; no prompts or response content |
| Context trimming | Keeps recent messages from a user-turn boundary | Avoids starting a request with orphaned tool outputs |
| Tool-call limits | Maximum rounds and calls per turn | Stops uncontrolled agent loops |
| Private thinking display | Filters explicit Qwen think tags | Does not guarantee every serving stack exposes thought in this format |

The agent uses Python's standard library only and is restricted to http://127.0.0.1:1234/v1 (or another loopback host). It does not browse the internet, execute shell commands, execute arbitrary generated code, or write project files. Persistent memory and diagnostic traces are local and git-ignored.

## 4. Evaluation strategy

The current suite has 29 single-turn tests and 6 turns across multi-turn scenarios: 35 records per full run. Reasoning Engine v2 cases cover:
- Arithmetic with a verification step
- Logical non-entailment and counterexamples
- Distinguishing observed facts from accusations
- Ordered planning with dependencies
- Backup, validation and rollback for a migration
- Trade-offs and explicit assumptions
- Infeasible time constraints

Three statuses have deliberately different meanings:
- **PASS:** A narrow deterministic check succeeded; not a certificate of general reasoning ability.
- **FAIL:** A strong mechanical check failed or a clearly unsafe claim was detected.
- **REVIEW:** Meaning, language naturalness, and nuanced reasoning require semantic/human review.

The evaluator was made more conservative around negation and question clauses so repeating a false proposition in a question is not automatically considered an endorsement. This is a heuristic guard, not a full natural-language understanding solution.

## 5. What CI does and does not prove

GitHub Actions validates Python syntax, benchmark JSON/schema, evaluator regressions, path safety, calculator restrictions, memory-save policy, context trimming, hidden-thinking filtering, and a mocked tool-call cycle.

CI does **not** run Qwen3-8B. Only running PHANTOM on the target PC verifies how its exact LM Studio version, model file, and chat template handle function calls. A model can choose the wrong tool, produce malformed arguments, or fail to use tools; the runtime must surface those outcomes rather than claiming an untested capability works.

## 6. Next engineering stages

### Stage A — Confirm a live tool call
Run the interactive assistant and ask for a multi-step calculation that should call calculator. Inspect whether the actual model requests a tool and whether the result is used correctly. If tool calling is not supported by the current LM Studio model/chat template, record the exact response and add a compatibility path; do not silently assume tools are working.

### Stage B — Review Reasoning Engine v2 output
Run the current benchmarks after syncing. Compare results only when evaluator and benchmark versions match. For each failure, inspect the local detailed report to separate a model mistake from an evaluator false positive. The public report deliberately excludes raw prompts and model generations.

### Stage C — Add reliability features using observed failures
Prioritize recurring failure classes. Potential additions include strict schemas for plans, deterministic final-condition checklists, a dry-run permission model for any future write tool, and a recovery strategy for malformed tool calls. Each addition must have positive and negative regression tests.

### Stage D — Consider learning only after evaluation is stable
Prompts and tools are system-level improvements, not weight training. Fine-tuning is a separate optional experiment that needs a curated, permissioned dataset and a held-out test set. Do not fine-tune until the scaffold shows repeatable gaps that prompts and tools cannot address.

## 7. Safety and privacy non-goals

- No arbitrary shell/code tool.
- No outbound model endpoint; loopback only.
- No automatic upload of detailed model responses.
- No storing memory unless the user explicitly asks to save something.
- No claim that passing a benchmark makes the assistant equivalent to frontier hosted models.
