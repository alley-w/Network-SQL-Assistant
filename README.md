# Network SQL Assistant

A learning project toward a text-to-SQL assistant for network monitoring.
Current features: a Docker-based SQL lab, reference-query evaluation, and a
configurable SQL-generation CLI. A live model connection still requires setup.
A web UI, interface utilization, and outage data are future work.
SQLBot is an architectural reference; this starter contains no copied SQLBot code.

## Run

Install and start Docker Desktop on your Mac, then open this folder in VS Code.
From its terminal:

```sh
docker compose run --build --rm lab
```

At the `sql>` prompt:

```sql
SELECT * FROM devices;
```

Type `quit` to exit. Work through `exercises.sql` one statement at a time.
After editing Python files, run the same Docker command to rebuild.

## What the Docker files do

- `Dockerfile` builds an image containing Python and our application.
- `compose.yaml` defines the lab container and a named volume for the database.
- A container is a running instance of the image. `--rm` removes that container
  after exit; the named volume keeps the database between runs.
- No host Python installation or exposed ports are needed. The SQL lab and
  reference evaluator require no API key.

## Generate SQL from a question

First inspect exactly what the model will receive, without making an API call:

```sh
docker compose run --build --rm lab python generate.py --preview "Which devices recorded CPU above 80%?"
```

`generate.py` reads the database's table definitions and combines them with SQL
instructions and your question. It sends schema and question, not metric rows.
Reference answers in `examples.json` are not included in the prompt.

Copy `.env.example` to `.env` and configure `LLM_BASE_URL`, `LLM_MODEL`, and,
if your service needs one, `LLM_API_KEY`. Compose passes those values to the
container. `.env` is excluded from Git and the Docker build context. Never paste
keys into source files or chat. Hosted API use may incur provider charges.

```sh
docker compose run --build --rm lab python generate.py "Which devices recorded CPU above 80%?"
```

This uses the OpenAI-compatible `/chat/completions` protocol with a configurable
model. OpenAI's base URL is `https://api.openai.com/v1`. For Ollama running on
your Mac, use `http://host.docker.internal:11434/v1` and an installed model name.
Inside the container, `localhost` refers to the container itself, not your Mac.

By default, output is untrusted model text for review only. To execute it:

```sh
docker compose run --build --rm lab python generate.py --execute "Which devices recorded CPU above 80%, and how many such samples did each have? Sort by hostname."
```

`query.py` opens a new read-only connection, enables query-only mode, and uses
SQLite's authorizer to allow SELECT, reads of the three application tables, and
an explicit list of reporting functions. Other actions are denied, including
writes, schema changes, PRAGMA, ATTACH, extension loading, and metadata reads.
SQLite rejects multiple statements; nonrecursive read CTEs are supported.
The prompt's instructions alone do not enforce these restrictions.

A progress handler interrupts expensive SQL after a two-second budget. This is
cooperative, not a hard process deadline, and does not bound every native call
or total process memory. SQL length, expression depth, column count, and individual
value size are also constrained. Results return at most 100 rows, with a
`truncated` flag when more exist. These are prototype controls for our small
synthetic SQLite database, not a production isolation boundary. They do not
establish whether the generated query correctly answers the question.

Run execution tests without contacting a model:

```sh
docker compose run --build --rm lab python -m unittest -v test_query
```

The tests cover reference answers, writes, attachment/extension attempts,
multiple statements, CTEs, result truncation, and expensive-query interruption.

Protocol references: [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat)
and [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).

## Data model

`sites` → `devices` → `device_metrics`: each device belongs to one site, and each
metric row belongs to one device. The composite metric key prevents duplicate
samples for a device and timestamp. CPU and memory are percentages, not counters.

The seed produces 3 sites, 6 devices, and 1,008 hourly samples for November 1–7,
2026, in UTC. A fixed random seed makes data reproducible. Device 3 has CPU spikes.
This small dataset illustrates queries, not a realistic production workload.

The interactive connection opens the database read-only. Output is capped at
100 rows; the interactive lab is intended for manually entered SQL. Automatic
model execution uses the separate restrictions in `query.py` described above.

## Learning path

### Reference questions

`examples.json` pairs five English questions with reference SQL and expected rows.
They cover counting, joins, grouping, threshold filtering, UTC date boundaries,
and an empty result. Run them inside Docker:

```sh
docker compose run --build --rm lab python evaluate.py
```

The evaluator creates a temporary seeded database, opens it read-only, compares
each query's rows with the saved answer, and exits nonzero on failure. It leaves
the lab volume untouched. Row order matters; multirow examples explicitly sort.

These checks verify our reference queries, not model accuracy. Later we will run
model-generated SQL against the same answers. Matching results on one dataset
does not prove two queries mean the same thing, and five examples are only a
starting point. Keep separate held-out questions when evaluating model changes.

Try changing `> 80` to `< 80` in the high-CPU example, rerun, observe the failure,
then restore it. This demonstrates why valid SQL can still answer the wrong question.

### Live model evaluation

```sh
docker compose run --build --rm lab python evaluate_model.py
```

This makes five paid model calls, generates SQL from questions and schema only,
executes through `query.py` against a fresh synthetic database, and compares
ordered result rows with the reference answers. It distinguishes generation
errors, execution errors, wrong results, and passes. Truncated results never
count as passes. Column aliases are not scored.

The detailed report persists in the Docker volume at `/app/data/model-evaluation.json`;
each run overwrites it. Reports include generated SQL, rows, per-question latency,
the configured model, UTC timestamp, and prompt/reference-set hashes. No API key
is included. A nonzero exit status means at least one question failed.

`benchmarks/baseline.json` records the first live run: GPT-4.1 mini answered 5/5
development questions correctly, with observed latency 0.867–1.816 seconds per
question (generation plus execution). This is one run on five simple development
questions, not held-out or production accuracy. The model alias can change over
time. Future evaluation needs more questions, unsupported requests, diverse data,
and separate held-out examples. Empty-result matches can conceal incorrect SQL.

### Challenge evaluation and abstention

`challenge_cases.json` contains six additional SQL questions and three requests
the schema cannot answer: interface utilization, downtime, and a relative date
without a reference date. Run it separately from the development examples:

```sh
docker compose run --build --rm lab python evaluate_model.py --cases challenge_cases.json --report data/challenge-evaluation.json
```

This makes nine model calls. Reports separate answerable-query correctness from
unsupported-request handling. `UNSUPPORTED` is correct only for a question marked
unsupported; refusing an answerable question or generating SQL for an unsupported
one is scored as `wrong_abstention`. Unsupported questions do not execute SQL.
SQL execution failures and API failures remain separate categories.

The challenge cases were committed before their first model run, with the same
prompt used for the initial development baseline. This provides a small initial
generalization check, not an independent benchmark: one author designed the app,
prompt, and questions. Once results inform prompt changes, these cases become
development material; use new unseen cases for subsequent generalization claims.

`benchmarks/challenge-baseline.json` preserves the first run: 6/6 answerable
questions passed, and 2/3 unsupported questions were correctly declined (8/9
overall). The failure was “yesterday”: the model used SQLite `date('now', ...)`
instead of returning `UNSUPPORTED`, despite the prompt's requirement for a
reference date. Its SQL was not executed by the evaluator for that unsupported
case. The generation prompt was not changed after this run. This demonstrates
why read-only enforcement and answer correctness must be evaluated separately,
and motivates explicit reference-date handling before a user-facing interface.

### Explicit date context

The CLI now checks common English relative-time phrases before contacting the
model. `today`, `yesterday`, and `tomorrow` require `--reference-date YYYY-MM-DD`,
defined as a UTC calendar date. Python resolves the day and replaces the phrase
with an explicit date in the user message. The system clock is not consulted.

```sh
docker compose run --build --rm lab python generate.py --execute --reference-date 2026-11-04 "How many samples exceeded 80% CPU yesterday?"
```

This question becomes “How many samples exceeded 80% CPU on 2026-11-03 UTC?”
Without the reference date, it exits with code 2 and requests clarification
without a model call. Other detected phrases such as “last week” or “past 7 days”
require explicit dates. The detection uses a deliberately small English pattern
list, not complete natural-language date understanding; unfamiliar wording can
still reach the model. UTC day semantics also differ from a user's local day.
Future UI work should collect a structured date range rather than infer all dates
from unrestricted prose. Model SQL still needs result-based evaluation.

Evaluation reports label `decision_source` as `application` or `model`, so a
deterministic refusal cannot be mistaken for improved model reasoning. The first
challenge baseline remains unchanged to preserve the observed model failure.

### CI workflow

GitHub Actions builds the Docker image on pushes and pull requests, runs the
execution/evaluation tests, verifies reference answers, and checks prompt preview.
It does not receive an API key or make paid model calls. Live evaluation remains
an explicit local command.

### Planned work

1. Explain SELECT, JOIN, GROUP BY, HAVING, and time filtering using this data.
2. Add interfaces and outage events; define how utilization/downtime are measured.
3. Generate SQL from questions using the schema and a model.
4. Validate and execute queries with read-only access and execution limits.
5. Add a UI and evaluate against questions with known correct results.

Resume claims should reflect completed, measured work. This first milestone is
a containerized synthetic network monitoring database and SQL exploration tool.
