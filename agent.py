"""
A minimal data-question agent.

The agent takes a natural-language question, lets the LLM decide whether to call
the `query_data` tool, runs the tool, feeds the result back to the LLM, and
returns a final natural-language answer.

The agent depends only on the `LLM` interface from llm.py -- it must not care
which provider is behind it.

Protocol (what the LLM is told to produce):
  - To query the data, the model replies with ONLY a JSON object:
        {"tool": "query_data", "sql": "SELECT ..."}
  - To answer, the model replies with ONLY:
        {"answer": "..."}
"""

from __future__ import annotations

import json
from typing import List

from llm import LLM, Message, get_llm
from tools import load_programs_db, query_data

REFUSAL_FALLBACK = "Sorry, I couldn't process that question right now."

SYSTEM_PROMPT = """You are a data assistant. Answer questions about a SQLite table
named `programs` with columns:
  program_id (TEXT), program_name (TEXT), region (TEXT), sector (TEXT),
  year (INTEGER), budget_usd (INTEGER), people_served (INTEGER), status (TEXT).

sector is one of: health, education, energy.

To read the data, reply with ONLY a JSON object: {"tool": "query_data", "sql": "SELECT ..."}
When you can answer, reply with ONLY: {"answer": "..."}
If the data cannot answer the question, reply with {"answer": "..."} saying so.
Reply with JSON only -- no extra text.
"""

MAX_STEPS = 4


class Agent:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or get_llm()
        self.con = load_programs_db()

    def _get_decision(self, messages: List[Message]) -> dict:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                reply = self.llm.complete(messages)
                parsed = json.loads(reply)
                if not isinstance(parsed, dict) or not ({"tool", "answer"} & parsed.keys()):
                    raise ValueError(f"unexpected reply shape: {reply!r}")
                return parsed
            except Exception as e:
                last_error = e
        raise ValueError(f"LLM did not return a usable reply: {last_error}")

    def answer(self, question: str) -> str:
        """Run the question through the agent loop and return a final answer string."""
        if not isinstance(question, str) or not question.strip():
            return "Please provide a non-empty question."

        messages: List[Message] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question.strip()},
        ]

        for _ in range(MAX_STEPS):
            try:
                decision = self._get_decision(messages)
            except ValueError:
                return REFUSAL_FALLBACK

            if "answer" in decision:
                return str(decision["answer"])

            sql = decision.get("sql", "")
            try:
                rows = query_data(sql, self.con)
                tool_content = json.dumps(rows)
            except ValueError as e:
                tool_content = json.dumps({"error": str(e)})

            messages.append({"role": "assistant", "content": json.dumps(decision)})
            messages.append({"role": "tool", "content": tool_content})

        return "Sorry, I couldn't find an answer within the allotted steps."


if __name__ == "__main__":
    import sys

    agent = Agent()
    q = " ".join(sys.argv[1:]) or "How many programs are in the education sector?"
    print(agent.answer(q))
