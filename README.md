# PHANTOM Lab

Automatic local-model experiments and reports for **PHANTOM**, using Qwen through LM Studio.

## Design

- Inference stays on your Windows PC via LM Studio's OpenAI-compatible local server.
- The runner refuses non-loopback API URLs. It is intended for `http://127.0.0.1:1234/v1` only.
- Benchmarks are versioned in `tests/benchmarks.json`.
- Runtime behavior rules are maintained in `prompts/guardrails.md` and appended to every system prompt by the runner, including when `config.local.json` already exists.
- Every run creates detailed Markdown and JSONL results in `local_reports/` and `local_results/`. These are git-ignored.
- The only report designed for GitHub is `public_reports/latest.md`: timestamp, model label, predefined test IDs/categories, and status counts. It does **not** include prompts, generated answers, raw exception text, or personal chat history.
- `run_phantom.bat` runs the suite and pushes only the safe summary when this repository is cloned with Git and push access is configured. If publishing fails, local reports remain available.

## Interactive local assistant

The experimental agent runtime is separate from the benchmark runner. It uses the same local LM Studio endpoint and standard-library Python only.

On Windows, first run `run_phantom.bat` to sync the latest code and execute the benchmark suite, then double-click `run_phantom_assistant.bat`. Or from PowerShell in the repository folder:

```powershell
python phantom_assistant.py
```

The assistant has a bounded, allow-listed tool loop: exact arithmetic, local computer time, safe workspace search/read, and opt-in local memory. It does not execute shell commands or arbitrary code, browse the internet, or write project files. Memory is stored under the ignored `memory/` folder and can only be saved when the current user message explicitly requests it; no conversation transcript is persisted. Tool traces contain only tool names/status/timing and are ignored by Git. LM Studio's OpenAI-compatible endpoint/model chat template must support tool calling for those tools to work.

## First-time setup on Windows

Requirements: Python 3.12 (or a compatible modern Python) and Git. LM Studio should be running Qwen3-8B with the local server enabled on port 1234.

In PowerShell, run:

```powershell
git clone https://github.com/zrajibj/phantom.git "$env:USERPROFILE\phantom-control"
& "$env:USERPROFILE\phantom-control\run_phantom.bat"
```

Sign into GitHub through Git Credential Manager if Git asks for authentication on push. Do not paste tokens into the script or config.

On future runs, double-click `run_phantom.bat` inside `phantom-control`. It will create `config.local.json` from the example on first run. That local file is ignored by Git.

## Manual run

```powershell
python phantom_lab.py --config config.local.json
```

No external Python packages are needed. The runner calls only the local LM Studio endpoint.

## Reading results in ChatGPT

After the safe summary is pushed, ChatGPT can read:

[public_reports/latest.md](https://github.com/zrajibj/phantom/blob/main/public_reports/latest.md)

Ask for an analysis of the latest PHANTOM run. For detailed diagnosis, inspect or attach `local_reports/latest.md`; full responses intentionally stay on your own PC by default.

## Evaluator confidence levels

- `PASS`: only for a narrow deterministic check such as exact output, required numeric values appearing as numeric tokens, guarded unknown-fact honesty, or a valid numbered list. This still does not prove the entire explanation is correct.
- `FAIL`: a deterministic mismatch or a clearly detected unsafe/contradictory claim.
- `REVIEW`: any quality or reasoning judgment that depends on meaning, naturalness, empathy, or context. A matching keyword or correct script alone is not enough to pass.
- `ERROR`: the model could not be called or the test could not complete.

The evaluator is deliberately conservative. Numeric checks verify that requested values appear, not that every sentence is mathematically valid. Logic and causal reasoning remain `REVIEW` unless a clearly contradictory response is detected. Treat results as diagnostics, not a scientific measure of general intelligence.

## Security

Never commit `config.local.json`, credentials, local result files, or personal conversation logs. The repository may be public; do not place private inputs into the tracked report. If you decide to publish full transcripts later, make the repository private first and explicitly change the reporting policy.
