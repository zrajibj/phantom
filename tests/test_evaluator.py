import unittest

from phantom_lab import evaluate


class EvaluatorTests(unittest.TestCase):
    def test_exact_output_passes_only_on_exact_match(self):
        self.assertEqual(evaluate("cold", {"exact": "cold"}, "deterministic")["status"], "PASS")
        self.assertEqual(evaluate("The answer is cold.", {"exact": "cold"}, "deterministic")["status"], "FAIL")

    def test_numeric_values_do_not_match_as_substrings(self):
        self.assertEqual(evaluate("Speed is 50 km/h.", {"numeric_values": [50]}, "deterministic")["status"], "PASS")
        self.assertEqual(evaluate("Speed is 150 km/h.", {"numeric_values": [50]}, "deterministic")["status"], "FAIL")

    def test_wallet_unknown_guard_accepts_honesty(self):
        result = evaluate(
            "Ami tomar wallet dekhte pari na, tai koto taka ache bolte parbo na.",
            {
                "unknown_claim": True,
                "uncertainty_signals": ["wallet dekhte pari na", "ami jani na"],
                "forbidden_claims": ["wallet e taka nai"],
            },
            "deterministic",
        )
        self.assertEqual(result["status"], "PASS")

    def test_wallet_unknown_guard_rejects_invented_balance(self):
        checks = {
            "unknown_claim": True,
            "uncertainty_signals": ["don't know", "cannot access"],
            "forbidden_claims": ["wallet e taka nai"],
        }
        self.assertEqual(evaluate("I don't know, maybe 100 taka.", checks, "deterministic")["status"], "FAIL")
        self.assertEqual(evaluate("Your wallet has no money.", checks, "deterministic")["status"], "FAIL")

    def test_logic_positive_claim_fails_but_correct_logic_requires_review(self):
        checks = {
            "semantic_rule": "non_entailment",
            "negative_claims": ["does not follow", "cannot conclude"],
            "positive_claims": ["it follows that some roses"],
        }
        wrong = evaluate("Yes, it follows that some roses fade quickly.", checks, "qualitative")
        good = evaluate("No, it does not follow; those flowers may not be roses.", checks, "qualitative")
        self.assertEqual(wrong["status"], "FAIL")
        self.assertEqual(good["status"], "REVIEW")

    def test_script_detection_never_certifies_language_quality(self):
        result = evaluate(
            "Bhai, ajke kichu korte iccha kortese na.",
            {"script": "latin"},
            "qualitative",
        )
        self.assertEqual(result["status"], "REVIEW")

    def test_numbered_fruit_list_requires_exact_items_and_no_extra_prose(self):
        checks = {
            "numbered_items": 3,
            "allowed_items": ["apple", "banana", "orange"],
            "only_numbered_items": True,
        }
        good = evaluate("1. Apple\n2. Banana\n3. Orange", checks, "deterministic")
        bad = evaluate("Here you go:\n1. Apple\n2. Banana\n3. Orange", checks, "deterministic")
        self.assertEqual(good["status"], "PASS")
        self.assertEqual(bad["status"], "FAIL")

    def test_qualitative_positive_keyword_is_not_a_pass(self):
        result = evaluate(
            "I understand. Maybe you should go for a walk.",
            {"any": ["understand"]},
            "qualitative",
        )
        self.assertEqual(result["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main(verbosity=2)
