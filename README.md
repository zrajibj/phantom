# PHANTOM Lab

Automatic local-model experiments and reports for **PHANTOM**, using Qwen through LM Studio.

## Design

- Inference stays on your Windows PC via LM Studio's OpenAI-compatible local server.
- The runner refuses non-loopback API URLs. It is intended for `http://127.0.0.1:1234/v1` only.
- Benchmarks are versioned in `tests/benchmarks.json`.
- Every run creates detailed Markdown and JSONL results in `local_reports/` and `local_results/`. These are git-ignored.
- The only report designed for GitHub is `public_reports/latest.md`: timestamp, model label, predefined test IDs/categories, and status counts. It does **not** include prompts, generated answers, raw exception text, or personal chat history.
- `run_phantom.bat` runs the suite and pushes only the safe summary when this repository is cloned with Git and push access is configured. If publishing fails, local reports remain available.

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

## Evaluator limitations

Checks in this first version are deterministic keyword/script/format screens, not a perfect judge of truth or language quality. Qualitative cases are marked `REVIEW` instead of being falsely declared passed. Treat results as diagnostics, not a scientific measure of general intelligence.

## Security

Never commit `config.local.json`, credentials, local result files, or personal conversation logs. The repository may be public; do not place private inputs into the tracked report. If you decide to publish full transcripts later, make the repository private first and explicitly change the reporting policy.
