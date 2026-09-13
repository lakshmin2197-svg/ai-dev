# Mini Research Assistant Agent — Take-Home Exercise

Thanks for taking the time to work through this. It's a small, deliberately
straightforward exercise meant to mirror the kind of work this role does day to
day: turning a researcher's ad-hoc questions into a small, reliable, AI-powered
tool. There are no trick questions and no clever algorithms required. We're more
interested in how you structure things and the trade-offs you reason about than
in volume of code.

**Time budget: ~2 hours.** If you run short on time, prioritize a working agent
and a working eval over polish, and use the README notes (Task 5) to describe
what you'd have done next.

## The scenario

A researcher has a small dataset of community programs (`data/programs.csv`) and
keeps asking questions about it in plain English: *"How many programs are in the
education sector?"*, *"What's the total budget?"*, and so on. You're building a
small agent that answers those questions by querying the data, and you're making
it reliable enough to trust and easy to evaluate.

The dataset is synthetic. Each row is a program with these columns:

| column | type | notes |
|---|---|---|
| `program_id` | text | e.g. `P001` |
| `program_name` | text | |
| `region` | text | Northeast, Southeast, Midwest, West, Southwest |
| `sector` | text | `health`, `education`, or `energy` |
| `year` | integer | 2019–2023 |
| `budget_usd` | integer | |
| `people_served` | integer | |
| `status` | text | active, completed, planned, cancelled |

## What's in the repo

```
data/programs.csv      ~150 rows of synthetic data (provided)
eval/questions.jsonl   ~10 question/expected-answer pairs (provided)
llm.py                 provider-agnostic LLM interface + an offline FakeLLM (provided)
tools.py               the query_data tool  -> YOU IMPLEMENT
agent.py               the agent loop        -> YOU IMPLEMENT
evaluate.py            the eval harness      -> YOU IMPLEMENT (the scorer)
requirements.txt       optional extras; the offline path needs only stdlib
```

### No API keys needed

`llm.py` ships a deterministic `FakeLLM` so the whole thing runs offline with no
keys and no cost. The agent talks to the `LLM` interface, never to a provider
directly. `FakeLLM` already knows how to handle the questions in the eval set, so
you can focus on the agent, the tool, and the harness. You should not need to
edit `FakeLLM`.

## Your tasks

1. **Implement the agent loop** in `agent.py` (`Agent.answer`). Given a question,
   let the LLM decide whether to call the `query_data` tool, run it, feed the
   result back, and return a final natural-language answer. The expected
   request/response JSON protocol is documented at the top of `agent.py`.

2. **Implement the tool** in `tools.py` (`query_data`). It runs a read-only SQL
   query against the data. Make it safe (SELECT-only) and make sure a bad query
   can't crash the agent. The CSV-to-SQLite loading is already done for you.

3. **Implement the scorer** in `evaluate.py` (`score_answer`) and run the harness.
   It should report a pass rate over `eval/questions.jsonl`. Note there are two
   kinds of question: `value` (the answer should contain an expected value) and
   `refusal` (questions the data can't answer, which the agent should decline).

4. **Add basic reliability.** Validate inputs, handle tool/parse errors, and
   retry the model call once before giving up. Keep the eval harness running even
   when an individual question fails.

5. **Write a short "Production notes" section** at the bottom of this README (a
   few bullets each is fine):
   - How would you swap `FakeLLM` for a real provider, and how would you keep the
     code provider-agnostic? (`llm.py` has a stub to point at.)
   - How would you evaluate and monitor reliability if this ran in a regulated,
     research environment?
   - Where would cost and latency come from, and how would you keep them in check?
   - What would move this from CSV to PostgreSQL, and how would you deploy it?
   - When (if ever) would you add a second agent?

## Running it

```bash
python evaluate.py                                          # run the eval harness
python agent.py "What is the total budget across all programs?"   # ask a single question
```

To switch providers later: `LLM_PROVIDER=fake` (default) or `LLM_PROVIDER=real`
(stub — intentionally not implemented).

## What we're looking for

Clear structure, sensible boundaries between the agent / tool / provider, honest
error handling, a meaningful eval, and thoughtful production notes. Working and
simple beats clever and fragile.

## Deliverables

- Working `agent.py`, `tools.py`, and `evaluate.py` (eval harness runs and reports
  a pass rate).
- The "Production notes" section below, filled in.

---

## Production notes

The design goal throughout was to keep three things separate: the thing that
decides (the LLM), the thing that acts (the tool), and the thing that checks
(the eval). That separation is what makes most of the following possible
without a rewrite.

**Provider swap.** `agent.py` never imports a provider SDK — it only calls
`self.llm.complete(messages)`, so `RealLLM.complete` in `llm.py` is the only
place that changes. It would translate our `{"role", "content"}` messages into
whatever shape the provider's chat API expects, call it, and return the raw
text. Two things to get right so it stays swappable later: keep the JSON
tool-call protocol in the system prompt itself rather than leaning on a
provider's native function-calling API (that would mean re-parsing per
provider), and keep credentials/model names in environment variables so
switching is a config change, not a code change.

**Reliability in a regulated setting.** A 10-question eval is a smoke test,
not a monitoring strategy. In production I'd want three layers: a much larger,
versioned regression set that runs in CI on every prompt/tool/provider change
(and specifically includes adversarial inputs — prompt injection attempts,
SQL-shaped questions, PII-shaped questions); structured logging of every
request — question, full message trace including the SQL that ran, final
answer, latency, token count — so any answer can be reconstructed and audited
after the fact, which matters more in a research/compliance context than in a
typical consumer app; and a thin human-review layer sampling live answers,
since an automated eval only ever catches the failure modes someone thought to
write a test for. I'd track pass rate split by category (value vs. refusal)
rather than one blended number, since a regression in one category is easy to
lose in an average.

**Cost, latency, concurrency, and scale.** Cost and latency both scale with
LLM round-trips per question — today that's up to `MAX_STEPS`, so capping it
low is already the main lever, alongside using a cheap/fast model for the
tool-vs-answer decision and reserving anything larger for the final synthesis
step. But the current code has a concurrency problem worth naming honestly:
`Agent.__init__` opens one SQLite connection per `Agent` instance and holds it
for the object's lifetime, and a default SQLite connection isn't safe to share
across threads. A single long-lived `Agent` serving concurrent requests would
either serialize on that connection or crash — neither is acceptable at any
real scale. The fix is to stop treating the DB connection as agent state:
either open a short-lived connection per request, or move to Postgres and pull
a connection from a pool per call. From there, scaling out is standard web
service shape — a stateless process per request/worker behind a load
balancer, horizontal autoscaling on request volume, and a connection pool
sized to the DB rather than to any single process. The one thing that doesn't
scale by adding more machines is the LLM provider's own rate limit, so that's
worth a request queue or backpressure mechanism once volume is real, plus
caching for repeated or near-duplicate questions to avoid paying for the same
round-trip twice.

**CSV to Postgres.** `query_data`'s validation logic barely changes — it's
still "reject anything that isn't a single safe SELECT," just against
`psycopg`/`SQLAlchemy` instead of `sqlite3`. What does change: run those
queries as a dedicated read-only DB role as a second layer of defense below
the application-level checks, add a statement timeout and a row cap so a wide
query can't return unbounded data or tie up a connection, and get a real
connection pool since (per above) that's now load-bearing for concurrency, not
optional. For deployment: package the agent behind a small stateless HTTP
service (FastAPI is a natural fit given the existing type hints), run it in a
container so it scales horizontally, point it at a managed Postgres instance,
and keep secrets in a secrets manager rather than env files once it's not just
running on a laptop.

**A second agent.** Not for this problem — it's one bounded skill (turn a
question into a query, turn a query result into a sentence), and splitting
that into multiple agents would add coordination cost without removing any
real complexity. I'd reach for a second agent only when a genuinely distinct
skill shows up that wants its own prompt, tools, or even model — for example,
a planner that decomposes a multi-part question into several queries for a
simpler executor to run, or a reviewer that checks a sensitive answer before
it goes out in a compliance-heavy setting. Until there's a concrete case like
that, one agent with one tool is easier to test, debug, and reason about than
a small multi-agent system would be.
