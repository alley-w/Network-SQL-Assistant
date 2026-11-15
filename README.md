# Network SQL Assistant

A learning project toward a text-to-SQL assistant for network monitoring.
Current features: a Docker-based SQL lab, reference-query evaluation, and a
configurable SQL-generation CLI. A live model connection still requires setup.
A local browser interface supports question entry, optional UTC reference dates,
SQL review, restricted execution, and CSV downloads. Interface utilization and
outage data are future work.
SQLBot is an architectural reference; this starter contains no copied SQLBot code.

## Project structure

```text
network_sql/
  database.py          # Schema and synthetic seed data
  dates.py             # Deterministic date clarification
  llm.py               # Prompt construction and model HTTP client
  executor.py          # Restricted read-only SQL execution
  ui.py                # Streamlit navigation, question page, and session state
  views.py             # Data explorer and saved evaluation pages
  lab.py               # Interactive SQL terminal
  generate.py          # Generation CLI
  evaluate.py          # Reference-query checks
  evaluate_model.py    # Model scoring and reports
  fixtures/            # Reference and challenge question sets
tests/                 # Execution, date, evaluation, and UI tests
benchmarks/            # Recorded baseline reports
app.py, ui.py, ...      # Small entry points; existing commands still work
```

The UI and CLI share the same package code. Model calls live in `llm.py`;
SQL permissions and resource limits live in `executor.py`. Evaluations import
these same components. Keep framework code in the UI so it does not become a
dependency of the database or executor.

Streamlit is the current UI framework. Add FastAPI if a separate frontend or
external clients need an HTTP API. SQLAlchemy and Alembic become useful when
adding database backends and managed schema migrations. Generated SQL must
continue to pass through the restricted executor regardless of framework.

Run the offline suite with `docker compose run --build --rm lab python -m unittest discover -v`.

## Run

### Browser interface

```sh
docker compose up --build -d web
```

Open http://localhost:8501. The sidebar links to **Ask a question**, **Explore data**,
and **Evaluation results**. Explore data shows counts, schema, and table previews.
Evaluation results displays saved baselines and the latest reports from the data
volume, with failed-question filtering. These pages make no model calls.

On Ask a question, enter a question, optionally select a UTC reference
date, and click **Generate SQL**. Review the SQL and resolved question, then click
**Run query**. Changing the question or date clears the prior answer. Generation
makes a paid model call; running the generated SQL or downloading results does
not call the model again. An empty result, API failure, unsupported question, and
blocked query are shown separately. CSV downloads contain only displayed rows.

The web service binds to this Mac's loopback address. It is a local development
app without authentication; do not expose it as a public service. API credentials
remain in the server-side environment and are not rendered by the UI. Session
state retains the current answer during interactions but is not durable history.

```sh
docker compose stop web
```

### Terminal SQL lab

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

`network_sql/executor.py` opens a new read-only connection, enables query-only mode, and uses
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
docker compose run --build --rm lab python -m unittest -v tests.test_query
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
model execution uses the separate restrictions in `network_sql/executor.py` described above.

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
executes through `network_sql/executor.py` against a fresh synthetic database, and compares
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
docker compose run --build --rm lab python evaluate_model.py --cases network_sql/fixtures/challenge_cases.json --report data/challenge-evaluation.json
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

## Import a local monitoring snapshot

The first real-data integration uses a normalized JSON export. Map your monitoring
system's fields to this format and convert timestamps to UTC before exporting.
Use sanitized identifiers if necessary: the question and schema go to the model;
query results stay local. The importer does not anonymize your export.

```json
{
  "sites": [{"id": 1, "name": "Example site"}],
  "devices": [{"id": 1, "hostname": "router-01", "site_id": 1, "device_type": "router"}],
  "device_metrics": [{"device_id": 1, "collected_at": "2026-11-01 12:00:00", "cpu_pct": 92.0, "memory_pct": 43.0}]
}
```

Each array must contain at least one record. IDs must be positive integers;
percentages must be finite numbers from 0 to 100. Duplicate IDs/samples, missing
references, invalid timestamps, and unexpected fields are rejected. JSON exports
are capped at 20 MB. Imports create a new database and refuse to overwrite one.

To import a host file into the existing Docker volume (replace the source path):

```sh
docker compose run --build --rm -v /absolute/path/export.json:/import/export.json:ro lab python -m network_sql.import_snapshot /import/export.json data/snapshot.db
```

Set `NETWORK_DB_PATH=data/snapshot.db` in `.env`, then run:

```sh
docker compose up --build -d web
```

The UI, generator CLI, and SQL lab will use that snapshot. A configured missing
or incompatible database produces an error; it is never populated with demo rows.
Leave `NETWORK_DB_PATH` blank to return to synthetic data. Existing evaluations
and saved baselines continue to use their synthetic dataset and are not accuracy
measurements for the imported snapshot. A vendor-specific exporter and verified
real-data questions are the next integration steps.

## SolarWinds Orion adapter — offline development

`network_sql/adapters/solarwinds.py` maps exported Orion query responses into the
same snapshot contract other monitoring adapters will use. It does not connect
to SWIS, request credentials, or contain a live API client. The included responses
are authored simulations, not captures from a real Orion installation.

Try the full offline import without credentials:

```sh
docker compose run --build --rm lab python -m network_sql.adapters.solarwinds network_sql/fixtures/orion_nodes_simulated.json network_sql/fixtures/orion_history_simulated.json data/orion-simulated.db
```

Set `NETWORK_DB_PATH=data/orion-simulated.db` in `.env` and restart the web service
to explore it. This remains simulated data. Importing again requires a new output
filename; existing snapshots are never overwritten.

The fixture contains 2 sites, 3 devices, and 6 history records. The verified SQL
question “How many recorded CPU averages exceeded 80% per device?” returns:
`demo-east-router: 1`, `demo-west-router: 2`.

### Mapping contract

| Input field | Shared field | Meaning |
| --- | --- | --- |
| Nodes `NodeID` | devices.id | Preserved Orion node identifier |
| Nodes `Caption` | devices.hostname | Display caption, required to be unique in this prototype |
| Export alias `Site` | sites.name | Explicit deployment-specific grouping |
| Export alias `DeviceType` | devices.device_type | Explicit classification such as router or switch |
| History `NodeID` | device_metrics.device_id | Reference to exported inventory |
| History `DateTime` | collected_at | Explicit timezone converted to UTC |
| History `AvgLoad` | cpu_pct | Recorded average CPU percentage |
| History `AvgPercentMemoryUsed` | memory_pct | Recorded average memory percentage |

The underlying fields are documented in the official
[Orion.Nodes schema](https://solarwinds.github.io/OrionSDK/schema/Orion.Nodes.html)
and [Orion.CPULoad schema](https://solarwinds.github.io/OrionSDK/schema/Orion.CPULoad.html).
`Site` and `DeviceType` are our export aliases, not assumed built-in Orion fields.
Map them from verified custom properties or another explicit mapping at work;
we do not infer device types from model names or treat SNMP Location as a site.

Input files contain `{"results": [...]}` objects. Supply complete exported
results for a bounded time range, using a consistent aggregation tier. The adapter
does not fetch additional pages or detect an incomplete export. Normalize raw
SWIS date serialization to timezone-qualified ISO 8601 before import. Naive dates,
fractional seconds, null metrics, out-of-range percentages, duplicate node/time
pairs, and unknown nodes fail rather than being guessed, rounded, or filled in.
Overlapping archive tiers must be resolved explicitly before import.

Historical averages are not instantaneous measurements or maxima. A threshold
count refers to exported average records, not incidents or downtime; history
intervals may differ from the hourly synthetic demo. This adapter currently loses
interval duration and archive provenance in the shared schema. It therefore does
not support reliable duration calculations or weighted cross-interval averages.
Those require extending the shared metric model before real-data evaluation.

Live Orion compatibility, installed module/schema differences, authentication,
paging, archive selection, and the site's custom-property mapping remain to be
verified in an approved work environment.

### Verify the Orion demo questions

`network_sql/fixtures/orion_cases.json` contains 16 answerable questions and four
unsupported requests. They cover inventory, joins, CPU/memory thresholds, rankings,
UTC boundaries, empty results, and unavailable bandwidth/outage/instantaneous-peak
information. These are development cases, not an independent benchmark.

After importing the simulated Orion snapshot, verify the reference SQL offline:

```sh
docker compose run --build --rm lab python evaluate_model.py --database data/orion-simulated.db --cases network_sql/fixtures/orion_cases.json --reference-only --report data/orion-reference.json
```

This checks only the 16 supplied SQL answers. It makes no model requests and
explicitly marks the four unsupported questions as untested. Reports identify
`evaluation_mode=reference_sql`; passing is not evidence of model accuracy.
The Evaluation results page offers the resulting Orion reference report.

To evaluate generated answers later, explicitly run the paid model evaluation:

```sh
docker compose run --rm lab python evaluate_model.py --database data/orion-simulated.db --cases network_sql/fixtures/orion_cases.json --report data/orion-model-evaluation.json
```

Both commands read the selected database without seeding or modifying it. Without
`--database`, evaluation retains the original fresh synthetic-demo behavior.
