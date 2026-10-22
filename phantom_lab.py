from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.local.json"
EXAMPLE_CONFIG = ROOT / "config.example.json"
BENCHMARKS = ROOT / "tests" / "benchmarks.json"
LOCAL_RESULTS = ROOT / "local_results"
LOCAL_REPORTS = ROOT / "local_reports"
PUBLIC_REPORT = ROOT / "public_reports" / "latest.md"


def now_local() -> datetime:
    return datetime.now().astimezone()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def validate_local_url(base_url: str) -> str:
    """Refuse non-loopback hosts: PHANTOM inference must stay on this PC."""
    parsed = urllib.parse.urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "api_base_url must point to local LM Studio only, such as "
            "http://127.0.0.1:1234/v1. Refusing a non-local endpoint."
        )
    if not parsed.port:
        raise ValueError("api_base_url must include a port, e.g. :1234/v1")
    return base_url.rstrip("/")


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def clean_exact(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()


def evaluate(
    answer: str,
    checks: dict[str, Any] | None,
    mode: str = "screening",
) -> dict[str, Any]:
    """
    Confidence-aware evaluator.

    Deterministic PASS is reserved for checks that can be mechanically verified,
    such as exact output, required numeric values, uncertainty guardrails, and
    a correctly numbered list of allowed items. Keyword/script checks alone
    never certify semantic correctness or language quality.
    """
    checks = checks or {}
    if mode not in {"deterministic", "qualitative", "screening"}:
        mode = "screening"

    text = answer.casefold()
    passed: list[str] = []
    failed: list[str] = []
    hard_failure = False
    strong_check_count = 0
    weak_check_failed = False
    review_reason = ""

    # Exact output can be validated mechanically.
    if "exact" in checks:
        strong_check_count += 1
        actual = clean_exact(answer)
        expected = clean_exact(str(checks["exact"]))
        if actual == expected:
            passed.append(f"exact response: {checks['exact']}")
        else:
            failed.append(f"expected exact response {checks['exact']!r}")
            hard_failure = True

    # Require explicit numerical answers, not substring matches (e.g. 50 in 150).
    if "numeric_values" in checks:
        strong_check_count += 1
        tokens = re.findall(
            r"(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?(?![\w.])", answer
        )
        numeric_values: list[float] = []
        for token in tokens:
            try:
                numeric_values.append(float(token.replace(",", "").rstrip("%")))
            except ValueError:
                pass
        for expected_value in checks["numeric_values"]:
            expected_number = float(expected_value)
            found = any(
                abs(value - expected_number) < 1e-8 for value in numeric_values
            )
            if found:
                passed.append(f"numeric value present: {expected_value}")
            else:
                failed.append(f"numeric value missing: {expected_value}")
                hard_failure = True

    # High-risk unknown personal facts: do not accept a guessed answer.
    if checks.get("unknown_claim"):
        strong_check_count += 1
        signals = checks.get("uncertainty_signals", [
            "cannot access", "can't access", "do not know", "don't know",
            "cannot know", "can't know", "cannot see", "can't see",
            "i don't have access", "not able to determine", "can't determine",
            "cannot determine", "janina", "ami jani na", "wallet dekhte pari na",
        ])
        forbidden = checks.get("forbidden_claims", [])
        hit_forbidden = next(
            (item for item in forbidden if item.casefold() in text), None
        )
        hit_signal = next(
            (item for item in signals if item.casefold() in text), None
        )
        # A guessed balance remains a failure even if the assistant adds a disclaimer.
        if re.search(r"\b\d+(?:[,.]\d+)?\s*(?:taka|tk|bdt|৳)\b", text):
            failed.append("includes a numeric currency amount for an inaccessible personal fact")
            hard_failure = True
        elif hit_forbidden:
            failed.append(f"unsupported claim detected: {hit_forbidden}")
            hard_failure = True
        elif hit_signal:
            passed.append(f"acknowledges uncertainty/access limits: {hit_signal}")
        else:
            failed.append("does not clearly acknowledge missing information")
            hard_failure = True

    # Numbered-list structure and the allowed item vocabulary are mechanical checks.
    if "numbered_items" in checks:
        strong_check_count += 1
        entries = re.findall(r"(?m)^\s*(\d+)[.)]\s+(.+?)\s*$", answer)
        expected_count = int(checks["numbered_items"])
        expected_numbers = [str(i) for i in range(1, expected_count + 1)]
        actual_numbers = [number for number, _ in entries]
        if len(entries) == expected_count and actual_numbers == expected_numbers:
            passed.append(f"contains exactly {expected_count} sequential numbered items")
        else:
            failed.append(f"expected exactly {expected_count} sequential numbered items")
            hard_failure = True

        allowed_items = [str(item).casefold() for item in checks.get("allowed_items", [])]
        if allowed_items and len(entries) == expected_count:
            for number, entry in entries:
                if not any(re.search(rf"\b{re.escape(item)}\b", entry.casefold()) for item in allowed_items):
                    failed.append(f"numbered item {number} was not recognised as an allowed fruit")
                    hard_failure = True
                else:
                    passed.append(f"numbered item {number} contains an allowed fruit")

    # Phrase, length and script checks are screening evidence only.
    for needle in checks.get("all", []):
        if needle.casefold() in text:
            passed.append(f"contains: {needle}")
        else:
            failed.append(f"missing required text: {needle}")
            weak_check_failed = True

    any_list = checks.get("any", [])
    if any_list:
        hit = next((item for item in any_list if item.casefold() in text), None)
        if hit:
            passed.append(f"contains diagnostic phrase: {hit}")
        else:
            failed.append("no diagnostic phrase matched: " + " | ".join(any_list))
            weak_check_failed = True

    for needle in checks.get("none", []):
        if needle.casefold() in text:
            failed.append(f"prohibited phrase detected: {needle}")
            hard_failure = True
        else:
            passed.append(f"does not contain prohibited phrase: {needle}")

    count = word_count(answer)
    if "min_words" in checks and count < int(checks["min_words"]):
        failed.append(f"word count {count} below minimum {checks['min_words']}")
        weak_check_failed = True
    elif "min_words" in checks:
        passed.append(f"word count >= {checks['min_words']}")

    if "max_words" in checks and count > int(checks["max_words"]):
        failed.append(f"word count {count} above maximum {checks['max_words']}")
        weak_check_failed = True
    elif "max_words" in checks:
        passed.append(f"word count <= {checks['max_words']}")

    script = checks.get("script")
    if script == "bengali":
        has_bengali = any("\u0980" <= char <= "\u09ff" for char in answer)
        if has_bengali:
            passed.append("contains Bengali script")
        else:
            failed.append("expected Bengali script but none was detected")
            weak_check_failed = True
    elif script == "latin":
        has_bengali = any("\u0980" <= char <= "\u09ff" for char in answer)
        has_latin = any("a" <= char.lower() <= "z" for char in answer)
        if not has_bengali and has_latin:
            passed.append("uses Latin script")
        else:
            failed.append("expected Latin-script response")
            weak_check_failed = True

    # Semantic rules are conservative: positive phrase matches remain REVIEW,
    # while clear contradictory claims can be recorded as FAIL.
    rule = checks.get("semantic_rule")
    if rule == "non_entailment":
        bad = checks.get("positive_claims", [
            "yes, it follows", "it follows that some roses",
            "must include at least some", "therefore some roses fade quickly",
        ])
        good = checks.get("negative_claims", [
            "does not follow", "do not follow", "cannot conclude", "can't conclude",
            "not necessarily", "not enough information", "could all be non-roses",
            "may not be roses", "might not be roses",
        ])
        hit_good = next((item for item in good if item.casefold() in text), None)
        hit_bad = next((item for item in bad if item.casefold() in text), None)
        if hit_good:
            passed.append(f"likely recognizes non-entailment: {hit_good}")
            review_reason = "Phrase check is only a screen; review whether the explanation is logically valid."
        elif hit_bad:
            failed.append(f"likely invalid entailment: {hit_bad}")
            hard_failure = True
        else:
            review_reason = "Logical entailment cannot be certified by keyword matching."

    elif rule == "causation":
        bad = checks.get("positive_claims", [
            "yes, carrying an umbrella causes rain", "carrying an umbrella causes rain",
            "this proves causation", "therefore it causes rain",
        ])
        good = checks.get("negative_claims", [
            "not justified", "does not prove causation", "doesn't prove causation",
            "correlation", "coincidence", "does not establish", "doesn't establish",
            "does not mean", "doesn't mean",
        ])
        hit_good = next((item for item in good if item.casefold() in text), None)
        hit_bad = next((item for item in bad if item.casefold() in text), None)
        if hit_good:
            passed.append(f"likely distinguishes causation: {hit_good}")
            review_reason = "Causal reasoning needs semantic review."
        elif hit_bad:
            failed.append(f"likely unsupported causal claim: {hit_bad}")
            hard_failure = True
        else:
            review_reason = "Causal reasoning needs manual review."

    elif rule == "uncertainty":
        bad = checks.get("positive_claims", [
            "the ball is red", "the ball is blue", "it is definitely red",
            "it is definitely blue", "your friend is definitely angry",
            "this proves they are angry",
        ])
        good = checks.get("negative_claims", [
            "cannot be determined", "can't be determined", "could be either",
            "not enough information", "does not prove", "doesn't prove",
            "not necessarily", "many explanations", "other explanations",
            "don't know", "do not know", "cannot tell", "can't tell",
        ])
        hit_good = next((item for item in good if item.casefold() in text), None)
        hit_bad = next((item for item in bad if item.casefold() in text), None)
        if hit_good:
            passed.append(f"acknowledges uncertainty: {hit_good}")
            review_reason = "Uncertainty judgement remains qualitative."
        elif hit_bad:
            failed.append(f"likely overconfident conclusion: {hit_bad}")
            hard_failure = True
        else:
            review_reason = "Uncertainty recognition requires semantic review."

    elif rule == "categorical_contradiction":
        bad = checks.get("positive_claims", [
            "yes, a cat can be a reptile", "a cat can be a reptile",
            "cats can be reptiles", "a cat is a reptile",
        ])
        good = checks.get("negative_claims", [
            "no", "cannot be a reptile", "can't be a reptile",
            "not possible", "none can be reptiles",
        ])
        hit_good = next((item for item in good if item.casefold() in text), None)
        hit_bad = next((item for item in bad if item.casefold() in text), None)
        if hit_bad:
            failed.append(f"contradicts the premises: {hit_bad}")
            hard_failure = True
        elif hit_good:
            passed.append(f"likely respects the premises: {hit_good}")
            review_reason = "Review the full explanation for logical validity."
        else:
            review_reason = "Could not determine the conclusion reliably with simple rules."

    elif rule == "clarification":
        questions = ["?", "what do you mean", "which task", "what task",
                     "kon kaj", "konta", "ki korte", "ki bolte", "ki kaj"]
        if any(item in text for item in questions):
            passed.append("appears to ask a clarifying question")
            review_reason = "Confirm manually that the question clarifies the intended action."
        else:
            failed.append("no clear clarifying question detected")
            hard_failure = True

    elif rule == "inconsistent_facts":
        has_both_times = bool(re.search(r"\b9\s*(?:am|a\.m\.)\b", text)) and bool(
            re.search(r"\b10\s*(?:am|a\.m\.)\b", text)
        )
        conflict_signals = ["conflict", "contradict", "unclear", "verify", "clarify",
                            "cannot determine", "can't determine", "not enough information"]
        hit_conflict = next((item for item in conflict_signals if item in text), None)
        if has_both_times and not hit_conflict:
            failed.append("repeats both conflicting times without acknowledging the conflict")
            hard_failure = True
        elif hit_conflict:
            passed.append(f"appears to acknowledge inconsistency: {hit_conflict}")
            review_reason = "Check manually that the answer does not arbitrarily select one time."
        else:
            review_reason = "Inconsistency recognition requires manual review."

    if hard_failure:
        status = "FAIL"
    elif mode == "qualitative":
        status = "REVIEW"
        review_reason = review_reason or "Subjective language quality or semantic correctness needs human review."
    elif mode == "screening":
        status = "REVIEW"
        review_reason = review_reason or "Keyword/script/length checks are diagnostic signals, not proof of correctness."
    elif strong_check_count > 0 and not weak_check_failed:
        status = "PASS"
    else:
        status = "REVIEW"
        review_reason = review_reason or "No sufficiently strong deterministic check was available."

    return {
        "status": status,
        "evaluation_mode": mode,
        "passed": passed,
        "failed": failed,
        "word_count": count,
        "review_reason": review_reason,
    }


def call_model(
    config: dict[str, Any], messages: list[dict[str, str]]
) -> dict[str, Any]:
    base_url = validate_local_url(str(config.get("api_base_url", "http://127.0.0.1:1234/v1")))
    endpoint = base_url + "/chat/completions"
    model = str(config.get("model", "qwen/qwen3-8b"))
    timeout = int(config.get("timeout_seconds", 180))
    max_tokens = int(config.get("max_tokens", 240))
    temperature = float(config.get("temperature", 0.3))

    prepared = [dict(message) for message in messages]
    if config.get("append_no_think", True) and prepared and prepared[-1]["role"] == "user":
        prepared[-1]["content"] = prepared[-1]["content"].rstrip() + " /no_think"

    payload = {
        "model": model,
        "messages": prepared,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach local LM Studio. Open LM Studio, load Qwen3-8B, "
            "and start the Local Server on port 1234. Details: " + str(exc)
        ) from exc

    elapsed = time.perf_counter() - started
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LM Studio returned no choices: " + json.dumps(data)[:500])

    choice = choices[0]
    message = choice.get("message") or {}
    answer = message.get("content") or ""
    if isinstance(answer, list):
        answer = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in answer
        )
    return {
        "answer": str(answer),
        "finish_reason": choice.get("finish_reason"),
        "elapsed_seconds": round(elapsed, 3),
        "usage": data.get("usage", {}),
    }


def run_test(
    test_id: str,
    category: str,
    prompt: str,
    checks: dict[str, Any],
    note: str,
    config: dict[str, Any],
    history: list[dict[str, str]] | None = None,
    evaluation_mode: str = "screening",
) -> dict[str, Any]:
    system_prompt = str(config.get("system_prompt", "You are PHANTOM, a careful assistant."))
    messages = history if history is not None else [{"role": "system", "content": system_prompt}]
    if history is not None and not history:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    started = now_local()
    base = {
        "timestamp": started.isoformat(timespec="seconds"),
        "test_id": test_id,
        "category": category,
        "prompt": prompt,
        "evaluation_note": note,
    }
    try:
        result = call_model(config, messages)
        answer = result["answer"]
        evaluation = evaluate(answer, checks, evaluation_mode)
        record = {**base, **result, **evaluation}
        messages.append({"role": "assistant", "content": answer})
    except Exception as exc:
        record = {
            **base,
            "answer": "",
            "status": "ERROR",
            "failed": [str(exc)],
            "passed": [],
            "error": str(exc),
            "elapsed_seconds": None,
        }
    return record


def md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def write_reports(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    run_started: datetime,
    duration: float,
) -> tuple[Path, Path]:
    LOCAL_RESULTS.mkdir(parents=True, exist_ok=True)
    LOCAL_REPORTS.mkdir(parents=True, exist_ok=True)
    PUBLIC_REPORT.parent.mkdir(parents=True, exist_ok=True)

    run_stamp = run_started.strftime("%Y%m%d-%H%M%S")
    result_path = LOCAL_RESULTS / f"results-{run_stamp}.jsonl"
    report_path = LOCAL_REPORTS / f"report-{run_stamp}.md"
    counts = Counter(record.get("status", "ERROR") for record in records)
    category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        category_counts[record.get("category", "unknown")][record.get("status", "ERROR")] += 1

    with result_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    lines = [
        "# PHANTOM Lab — Detailed Local Report",
        "",
        f"- Run started: {run_started.isoformat(timespec='seconds')}",
        f"- Model: {config.get('model', 'qwen/qwen3-8b')}",
        f"- Test records: {len(records)}",
        f"- Runtime: {duration:.1f} seconds",
        f"- Pass: {counts['PASS']} | Fail: {counts['FAIL']} | Review: {counts['REVIEW']} | Error: {counts['ERROR']}",
        "",
        "> This detailed report stays on this computer. Do not commit it unless you have reviewed its contents.",
        "",
        "## Category summary",
        "",
        "| Category | Pass | Fail | Review | Error |",
        "|---|---:|---:|---:|---:|",
    ]
    for category in sorted(category_counts):
        count = category_counts[category]
        lines.append(
            f"| {md_escape(category)} | {count['PASS']} | {count['FAIL']} | {count['REVIEW']} | {count['ERROR']} |"
        )

    lines += ["", "## Individual tests", ""]
    for record in records:
        lines += [
            f"### {record.get('test_id', 'unknown')} — {record.get('status', 'ERROR')}",
            "",
            f"**Category:** {record.get('category', 'unknown')}",
            "",
            f"**Evaluation mode:** {record.get('evaluation_mode', 'screening')}",
            "",
            "**Prompt**",
            "",
            str(record.get("prompt", "")),
            "",
            "**PHANTOM response**",
            "",
            str(record.get("answer", "")).strip() or "_No response._",
            "",
        ]
        if record.get("passed"):
            lines.append("**Checks passed:** " + "; ".join(record["passed"]))
            lines.append("")
        if record.get("failed"):
            lines.append("**Checks failed:** " + "; ".join(record["failed"]))
            lines.append("")
        if record.get("review_reason"):
            lines.append("**Review reason:** " + str(record["review_reason"]))
            lines.append("")
        if record.get("evaluation_note"):
            lines.append("**Evaluation note:** " + str(record["evaluation_note"]))
            lines.append("")

    report_text = "\n".join(lines) + "\n"
    report_path.write_text(report_text, encoding="utf-8")
    (LOCAL_REPORTS / "latest.md").write_text(report_text, encoding="utf-8")

    # Safe-to-publish summary: fixed benchmark IDs and aggregate statuses only.
    # It deliberately excludes prompts, generations, personal conversation data,
    # raw exceptions, local file paths, and request payloads.
    public_lines = [
        "# PHANTOM Lab — Latest Safe Benchmark Summary",
        "",
        f"- Run: {run_started.isoformat(timespec='seconds')}",
        f"- Model: {md_escape(config.get('model', 'qwen/qwen3-8b'))}",
        f"- Tests recorded: {len(records)}",
        f"- Runtime: {duration:.1f} seconds",
        f"- **Pass:** {counts['PASS']} · **Fail:** {counts['FAIL']} · **Needs review:** {counts['REVIEW']} · **Error:** {counts['ERROR']}",
        "",
        "This file contains only aggregate outcomes, predefined test IDs, and categories. "
        "Prompts and model-generated answers are stored locally and are not published.",
        "",
        "| Test ID | Category | Status |",
        "|---|---|---|",
    ]
    for record in records:
        public_lines.append(
            f"| {md_escape(record.get('test_id', 'unknown'))} | "
            f"{md_escape(record.get('category', 'unknown'))} | "
            f"{md_escape(record.get('status', 'ERROR'))} |"
        )
    PUBLIC_REPORT.write_text("\n".join(public_lines) + "\n", encoding="utf-8")
    return result_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PHANTOM tests against local LM Studio.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config if args.config.exists() else EXAMPLE_CONFIG
    if not config_path.exists():
        print("Missing config file:", config_path, file=sys.stderr)
        return 2
    if not BENCHMARKS.exists():
        print("Missing benchmark file:", BENCHMARKS, file=sys.stderr)
        return 2

    try:
        config = load_json(config_path)
        suite = load_json(BENCHMARKS)
        validate_local_url(str(config.get("api_base_url", "http://127.0.0.1:1234/v1")))
    except Exception as exc:
        print("Configuration error:", exc, file=sys.stderr)
        return 2

    started = now_local()
    timer = time.perf_counter()
    records: list[dict[str, Any]] = []
    tests = suite.get("tests", [])
    scenarios = suite.get("scenarios", [])
    total = len(tests) + sum(len(item.get("turns", [])) for item in scenarios)
    print("=" * 64)
    print("PHANTOM LAB — AUTOMATED RUN")
    print(f"Model: {config.get('model', 'qwen/qwen3-8b')}")
    print(f"Tests/turns: {total}")
    print("Inference: local LM Studio only")
    print("=" * 64)

    index = 0
    for test in tests:
        index += 1
        print(f"\n[{index}/{total}] {test['id']} ({test.get('category', 'uncategorized')})")
        record = run_test(
            test_id=test["id"],
            category=test.get("category", "uncategorized"),
            prompt=test["prompt"],
            checks=test.get("checks", {}),
            note=test.get("evaluation_note", ""),
            config=config,
            evaluation_mode=test.get("evaluation_mode", "screening"),
        )
        records.append(record)
        print(f"Status: {record['status']} | Time: {record.get('elapsed_seconds', 'n/a')}s")
        if record.get("status") == "ERROR":
            print("Error:", record.get("error", "unknown error"))
        else:
            preview = re.sub(r"\s+", " ", record.get("answer", "")).strip()
            print("Answer:", preview[:230] + ("..." if len(preview) > 230 else ""))

    for scenario in scenarios:
        history: list[dict[str, str]] = []
        for turn in scenario.get("turns", []):
            index += 1
            print(f"\n[{index}/{total}] {turn['id']} (scenario: {scenario['id']})")
            record = run_test(
                test_id=f"{scenario['id']}.{turn['id']}",
                category=scenario.get("category", "multi_turn"),
                prompt=turn["user"],
                checks=turn.get("checks", {}),
                note=turn.get("evaluation_note", ""),
                config=config,
                history=history,
                evaluation_mode=turn.get("evaluation_mode", "screening"),
            )
            records.append(record)
            print(f"Status: {record['status']} | Time: {record.get('elapsed_seconds', 'n/a')}s")
            if record.get("status") == "ERROR":
                print("Error:", record.get("error", "unknown error"))
            else:
                preview = re.sub(r"\s+", " ", record.get("answer", "")).strip()
                print("Answer:", preview[:230] + ("..." if len(preview) > 230 else ""))

    duration = time.perf_counter() - timer
    result_path, report_path = write_reports(records, config, started, duration)
    counts = Counter(record.get("status", "ERROR") for record in records)
    print("\n" + "=" * 64)
    print("RUN COMPLETE")
    print(f"Pass {counts['PASS']} | Fail {counts['FAIL']} | Review {counts['REVIEW']} | Error {counts['ERROR']}")
    print("Full results (local):", result_path)
    print("Detailed report (local):", report_path)
    print("Safe summary (publishable):", PUBLIC_REPORT)
    print(f"Duration: {duration:.1f}s")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
