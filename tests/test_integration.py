import unittest

from agent import Agent
from evaluate import load_questions, score_answer


class TestEndToEndEval(unittest.TestCase):
    def test_all_eval_questions_pass(self):
        agent = Agent()
        questions = load_questions()
        failures = []
        for item in questions:
            answer = agent.answer(item["question"])
            ok = score_answer(answer, item.get("expected", ""), item.get("kind", "value"))
            if not ok:
                failures.append((item["id"], item["question"], answer))
        self.assertEqual(failures, [], f"failing questions: {failures}")


if __name__ == "__main__":
    unittest.main()
