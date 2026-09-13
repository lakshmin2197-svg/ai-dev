"""
Evaluation harness.

Runs every question in eval/questions.jsonl through the agent, scores the answer
against the expected result, and prints a pass rate.

Run:  python evaluate.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from agent import Agent

QUESTIONS_PATH = Path(__file__).resolve().parent / "eval" / "questions.jsonl"

_REFUSAL_MARKERS = (
    "don't have", "do not have", "cannot answer", "can't answer",
    "no information", "not available", "unable to answer", "don't know",
)


def load_questions(path: Path = QUESTIONS_PATH) -> List[Dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def score_answer(answer: str, expected: str, kind: str) -> bool:
    """
    Return True if `answer` is correct for this question.

    There are two kinds of question:
      - kind == "value":   the answer should contain the `expected` value
                           (e.g. a count, sum, or sector name).
      - kind == "refusal": there is no `expected` value; the answer is correct
                           if it acknowledges the data can't answer the question.

    """
    if not isinstance(answer, str):
        return False

    if kind == "refusal":
        lowered = answer.lower()
        return any(marker in lowered for marker in _REFUSAL_MARKERS)

    expected_norm = str(expected).strip().lower().replace(",", "")
    if not expected_norm:
        return False
    answer_norm = answer.lower().replace(",", "")
    return expected_norm in answer_norm


def main() -> None:
    agent = Agent()
    questions = load_questions()
    passed = 0

    for item in questions:
        try:
            answer = agent.answer(item["question"])
        except Exception as e:  # keep the harness running even if the agent fails
            answer = f"ERROR: {e}"

        try:
            ok = score_answer(answer, item.get("expected", ""), item.get("kind", "value"))
        except NotImplementedError:
            ok = False

        passed += int(ok)
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {item['id']}: {item['question']}")
        print(f"        expected={item.get('expected', '')!r} kind={item.get('kind')}")
        print(f"        answer={answer!r}")

    total = len(questions)
    print(f"\nScore: {passed}/{total} ({passed / total:.0%})" if total else "No questions.")


if __name__ == "__main__":
    main()
