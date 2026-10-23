# Todo app on EKS

A deliberately small full-stack CRUD app (React + FastAPI + Postgres) built to practise deploying on AWS EKS.
Design: `docs/superpowers/specs/2026-10-23-eks-todo-app-design.md`.

## Stage 1: run it locally

**Needs:** Docker with Compose. Nothing else; Python and Node run inside containers.

```bash
docker compose up --build        # first run builds both images
```

| URL | What |
|---|---|
| http://localhost:8080 | the app (nginx serves React, proxies `/api` to the backend) |
| http://localhost:8000/docs | FastAPI's auto-generated API docs (backend direct) |

Stop with `docker compose down` (add `-v` to also delete the database volume).

### How the pieces connect
```
browser -> frontend (nginx :8080) --/api--> backend (uvicorn :8000) --> postgres (:5432)
```
The backend reads `DATABASE_URL` from the environment. Compose sets it; on EKS a Kubernetes Secret will.
The frontend only ever calls relative URLs (`/api/todos`), so the same image works behind compose's nginx
and, later, behind the AWS load balancer.

### Tests
Unit tests need no database (in-memory SQLite). Integration tests need a real Postgres.
They **drop and recreate tables** in the database they point at, so use a separate one:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U todo todo_test        # once

# Backend: lint, unit, integration (run inside a container, no local Python needed)
docker run --rm --network host -v "$PWD/backend":/app -w /app \
  -e TEST_DATABASE_URL=postgresql+psycopg://todo:todo@localhost:5432/todo_test \
  python:3.12-slim sh -c "pip install -q -r requirements-dev.txt && ruff check . && ruff format --check . && pytest -q"

# Frontend: lint, unit tests, build
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/frontend":/work -w /work \
  node:22-slim sh -c "npm ci && npm run lint && npm test && npm run build"
```
(If you have Python 3.12 / Node 22 installed locally you can run `pytest`, `npm test` etc. directly.)

### CI
`.github/workflows/ci.yml` runs the same checks on every pull request (lint, unit tests, integration tests against a
Postgres service container, frontend build) and then builds both Docker images and scans them with Trivy.
The deploy workflow arrives in the EKS stage.

## Coming next
Stage 2 onward (AWS prerequisites, cluster, ALB controller, deploy, CloudFront, CI/CD deploy, teardown) is added as we build each piece.
