import json
import unittest

from agent import Agent, MAX_STEPS


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if not self.replies:
            raise RuntimeError("ScriptedLLM ran out of replies")
        return self.replies.pop(0)


class TestAgentAnswer(unittest.TestCase):
    def test_empty_question_is_rejected_without_calling_llm(self):
        llm = ScriptedLLM([])
        agent = Agent(llm=llm)
        result = agent.answer("   ")
        self.assertIn("non-empty", result.lower())
        self.assertEqual(llm.calls, 0)

    def test_direct_answer_no_tool_call(self):
        llm = ScriptedLLM([json.dumps({"answer": "There are 50 education programs."})])
        agent = Agent(llm=llm)
        result = agent.answer("How many education programs?")
        self.assertEqual(result, "There are 50 education programs.")
        self.assertEqual(llm.calls, 1)

    def test_tool_call_then_answer(self):
        llm = ScriptedLLM(
            [
                json.dumps(
                    {
                        "tool": "query_data",
                        "sql": "SELECT COUNT(*) FROM programs WHERE sector = 'education'",
                    }
                ),
                json.dumps({"answer": "There are 50 education programs."}),
            ]
        )
        agent = Agent(llm=llm)
        result = agent.answer("How many education programs?")
        self.assertEqual(result, "There are 50 education programs.")
        self.assertEqual(llm.calls, 2)

    def test_unsafe_sql_from_llm_does_not_crash_and_data_survives(self):
        llm = ScriptedLLM(
            [
                json.dumps({"tool": "query_data", "sql": "DROP TABLE programs"}),
                json.dumps({"answer": "I can't run that."}),
            ]
        )
        agent = Agent(llm=llm)
        result = agent.answer("Delete everything")
        self.assertEqual(result, "I can't run that.")
        rows = agent.con.execute("SELECT COUNT(*) FROM programs").fetchall()
        self.assertEqual(rows[0][0], 150)

    def test_malformed_json_retries_once_then_succeeds(self):
        llm = ScriptedLLM(["not json at all", json.dumps({"answer": "recovered"})])
        agent = Agent(llm=llm)
        result = agent.answer("anything")
        self.assertEqual(result, "recovered")
        self.assertEqual(llm.calls, 2)

    def test_malformed_json_twice_gives_up_gracefully(self):
        llm = ScriptedLLM(["nope", "still nope"])
        agent = Agent(llm=llm)
        result = agent.answer("anything")
        self.assertIsInstance(result, str)
        self.assertEqual(llm.calls, 2)

    def test_reply_missing_both_keys_is_treated_as_malformed(self):
        llm = ScriptedLLM(
            [json.dumps({"unexpected": "shape"}), json.dumps({"answer": "recovered"})]
        )
        agent = Agent(llm=llm)
        result = agent.answer("anything")
        self.assertEqual(result, "recovered")

    def test_endless_tool_requests_stop_at_max_steps(self):
        tool_reply = json.dumps(
            {"tool": "query_data", "sql": "SELECT COUNT(*) FROM programs"}
        )
        llm = ScriptedLLM([tool_reply] * (MAX_STEPS + 5))
        agent = Agent(llm=llm)
        result = agent.answer("anything")
        self.assertIsInstance(result, str)
        self.assertEqual(llm.calls, MAX_STEPS)


if __name__ == "__main__":
    unittest.main()
