# Network SQL Assistant

A learning project toward a text-to-SQL assistant for network monitoring.
Current milestone: a Docker-based SQL lab with synthetic data. Natural-language
SQL generation, a web UI, interface utilization, and outage data are future work.
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
- No host Python installation, packages, API keys, or exposed ports are needed.

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

1. Explain SELECT, JOIN, GROUP BY, HAVING, and time filtering using this data.
2. Add interfaces and outage events; define how utilization/downtime are measured.
3. Generate SQL from questions using the schema and a model.
4. Validate and execute queries with read-only access and execution limits.
5. Add a UI and evaluate against questions with known correct results.

Resume claims should reflect completed, measured work. This first milestone is
a containerized synthetic network monitoring database and SQL exploration tool.
