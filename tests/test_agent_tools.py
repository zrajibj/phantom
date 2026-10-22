import tempfile
import unittest
from pathlib import Path

import phantom_assistant as agent


class AgentToolTests(unittest.TestCase):
    def test_calculator_handles_basic_arithmetic(self):
        self.assertEqual(agent.calculate("(800 * 0.75)"), "600.0")
        self.assertEqual(agent.calculate("3 * 12 - 7"), "29")
        self.assertEqual(agent.calculate("2 ** 5"), "32")

    def test_chat_loop_executes_registered_tool_then_uses_model_final(self):
        original = agent.request_model
        responses = iter([
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-test-1",
                    "type": "function",
                    "function": {"name": "calculator", "arguments": "{\"expression\": \"3 * 12 - 7\"}"}
                }]
            },
            {"role": "assistant", "content": "There are 29 apples remaining."},
        ])
        calls = []

        def fake_request_model(config, messages, tools_enabled):
            calls.append(tools_enabled)
            return next(responses)

        agent.request_model = fake_request_model
        try:
            history = [
                {"role": "system", "content": "test system"},
                {"role": "user", "content": "Calculate remaining apples."},
            ]
            answer = agent.chat_turn({}, history, "Calculate remaining apples.")
            self.assertEqual(answer, "There are 29 apples remaining.")
            self.assertEqual(calls, [True, True])
            tool_messages = [m for m in history if m.get("role") == "tool"]
            self.assertEqual(len(tool_messages), 1)
            self.assertIn('"result": "29"', tool_messages[0]["content"])
        finally:
            agent.request_model = original

    def test_calculator_rejects_function_calls_and_names(self):
        with self.assertRaises(ValueError):
            agent.calculate("__import__('os').system('whoami')")
        with self.assertRaises(ValueError):
            agent.calculate("open(1)")
        with self.assertRaises(ValueError):
            agent.calculate("2 ** 999")

    def test_hidden_thinking_is_not_shown_to_user(self):
        self.assertEqual(agent.strip_hidden_thinking("<think>private scratch work</think>Final answer."), "Final answer.")
        self.assertEqual(agent.strip_hidden_thinking("<think>incomplete private scratch work"), "")

    def test_loopback_url_guard(self):
        self.assertTrue(agent.validate_local_url("http://127.0.0.1:1234/v1").endswith("/v1"))
        with self.assertRaises(ValueError):
            agent.validate_local_url("https://example.com/v1")
        with self.assertRaises(ValueError):
            agent.validate_local_url("http://192.168.1.12:1234/v1")

    def test_workspace_traversal_is_blocked(self):
        with self.assertRaises(ValueError):
            agent.safe_workspace_file("../README.md")
        with self.assertRaises(ValueError):
            agent.safe_workspace_file("config.local.json")
        with self.assertRaises(ValueError):
            agent.safe_workspace_file("memory/user_memory.json")

    def test_memory_requires_explicit_current_request(self):
        self.assertTrue(agent._explicit_save_requested("Remember this: I prefer short answers."))
        self.assertFalse(agent._explicit_save_requested("Don't remember this."))
        self.assertFalse(agent._explicit_save_requested("I prefer short answers."))

    def test_memory_value_must_be_exact_user_text(self):
        with tempfile.TemporaryDirectory() as folder:
            old_file = agent.MEMORY_FILE
            agent.MEMORY_FILE = Path(folder) / "user_memory.json"
            try:
                with self.assertRaises(PermissionError):
                    agent.memory_save({"key": "style", "value": "short answers"}, "I prefer short answers.")
                saved = agent.memory_save(
                    {"key": "style", "value": "I prefer short answers"},
                    "Remember this: I prefer short answers.",
                )
                self.assertTrue(saved["saved"])
                self.assertEqual(agent._load_memory()["style"], "I prefer short answers")
            finally:
                agent.MEMORY_FILE = old_file


if __name__ == "__main__":
    unittest.main(verbosity=2)
