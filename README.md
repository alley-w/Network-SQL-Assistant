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

Output is untrusted model text for review only: it is not validated or executed.
The prompt's read-only instructions are not a security boundary. Unsupported
questions should return `UNSUPPORTED`; that behavior still needs live evaluation.
The next milestone will validate and constrain execution before integrating it.

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
100 rows; this is a display cap, not a query execution limit. Before adding LLM
execution we will implement query validation and resource limits.

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

### Roadmap

1. Explain SELECT, JOIN, GROUP BY, HAVING, and time filtering using this data.
2. Add interfaces and outage events; define how utilization/downtime are measured.
3. Generate SQL from questions using the schema and a model.
4. Validate and execute queries with read-only access and execution limits.
5. Add a UI and evaluate against questions with known correct results.

Resume claims should reflect completed, measured work. This first milestone is
a containerized synthetic network monitoring database and SQL exploration tool.
