# EKS Todo App — Design

## Purpose
A minimal full-stack CRUD app whose real purpose is teaching the user how to deploy on AWS EKS.
The app stays deliberately small so the Kubernetes/AWS pieces are the focus.
The user is learning: at every stage the assistant explains what it is doing, and every
manual step is explicitly flagged and explained (why it is manual, what it does).

## Decisions
| Area | Choice |
|---|---|
| Backend | Python + FastAPI + SQLAlchemy |
| Frontend | React (Vite), served by nginx in its own container |
| Entity | Todo: `id`, `title`, `done` |
| Database | Postgres in-cluster: StatefulSet + gp3 EBS PVC (not production HA; README explains RDS swap) |
| Cluster | eksctl, region `us-east-1` |
| Exposure | One ALB via AWS Load Balancer Controller + Ingress; `/api` -> backend, `/` -> frontend |
| HTTPS | CloudFront in front of the ALB (no domain; `*.cloudfront.net` cert). CloudFront -> ALB over HTTP |
| Lockdown | ALB security group allows port 80 only from the CloudFront origin-facing prefix list |
| Registry | Amazon ECR (`todo-backend`, `todo-frontend`), images tagged with git SHA |
| Local dev | docker-compose (postgres, backend, frontend) |
| CI/CD | GitHub Actions, OIDC to AWS (no stored keys) |
| Out of scope | Helm/Kustomize, custom domain/ACM/ExternalDNS, RDS, frontend e2e tests |

## Architecture
```
Browser --HTTPS--> CloudFront --HTTP--> ALB (made by Ingress) -> /api -> backend Service -> backend pods -> postgres Service -> postgres StatefulSet (EBS)
                                                             \-> /    -> frontend Service -> frontend pods (nginx + built React)
```
Frontend calls relative `/api/todos` (single origin, no CORS).

## Repo layout
```
backend/    app/ (main, models, db, routes), tests/unit, tests/integration, Dockerfile, requirements
frontend/   Vite React app, Vitest tests, nginx.conf, Dockerfile (multi-stage)
k8s/        namespace, postgres (StatefulSet+Service), secret template, backend, frontend, ingress
eks/        cluster.yaml (eksctl), iam policy/notes for LB controller + EBS CSI
infra/      cloudfront.yaml (CloudFormation: distribution + ALB security group)
.github/workflows/  ci.yml (PRs), deploy.yml (main)
docker-compose.yml
README.md   staged runbook
```

## Backend
- Endpoints: `GET/POST /api/todos`, `GET/PUT/DELETE /api/todos/{id}`, `GET /api/healthz`.
- `DATABASE_URL` from env (Secret in cluster). Table created on startup (demo-grade; no migrations).
- Runs as non-root; liveness/readiness probes on `/api/healthz`.

## Frontend
- Single page: list, add, toggle done, delete. Fetches `/api/todos`.
- Multi-stage Dockerfile: node build -> nginx serving static files, SPA fallback.

## Kubernetes
- Namespace `todo`. Resource requests/limits and probes on all workloads.
- Postgres: single replica StatefulSet, `volumeClaimTemplates` on `gp3` StorageClass (EBS CSI).
- Secret holds DB credentials; the committed file is a template only, real secret is created manually.
- Ingress annotations: `alb.ingress.kubernetes.io/scheme: internet-facing`, `target-type: ip`,
  `security-groups: <CloudFront-only SG>`.

## Tests
- Backend unit: pytest on routes/validation with SQLite.
- Backend integration: pytest against real Postgres (compose locally, service container in CI), full CRUD over HTTP.
- Frontend unit: Vitest + React Testing Library, API mocked.
- Post-deploy smoke: curl CloudFront `/api/healthz` and `/api/todos`.

## CI/CD
- `ci.yml` on pull requests (no AWS access): ruff, eslint, unit tests, integration tests (Postgres service container),
  Docker build (no push), Trivy scan (fail on fixable HIGH/CRITICAL), kubeconform manifest validation.
- `deploy.yml` on push to main: repeat the checks, assume AWS role via OIDC, push images to ECR tagged with SHA,
  `kubectl apply` with the new tags, `kubectl rollout status` (fail on bad rollout), smoke test.
- `concurrency: { group: deploy-prod, cancel-in-progress: false }` so deploys run serially.
- `environment: production` so approvals / branch rules / OIDC subject restrictions can be attached.

## Staged README (each stage: what we do, why, and each manual step flagged)
1. **Local**: run via docker-compose, run tests. (Manual: install Docker.)
2. **AWS prerequisites**: CLI, eksctl, kubectl, helm; create ECR repos. (Manual: AWS credentials, billing awareness.)
3. **Cluster**: `eksctl create cluster` (~15 min); EBS CSI driver add-on.
4. **Ingress controller**: IAM policy, service account, install AWS Load Balancer Controller with helm.
   (Manual: one-time IAM setup; explained as the controller's identity to call AWS.)
5. **First deploy by hand**: build/push images, create Secret, `kubectl apply`, wait for ALB.
6. **CloudFront + security group**: read ALB hostname, create CloudFormation stack, apply SG annotation,
   test HTTPS. (Manual: chicken-and-egg ordering, explained.)
7. **CI/CD**: create GitHub OIDC provider and IAM role, set repo variables, create `production` environment, push to main.
8. **Teardown**: delete CloudFront stack, k8s resources (so ALB/EBS are removed), then the cluster, ECR repos.
   (Manual and important: ordering avoids orphaned billable resources.)

## Cost note
EKS control plane ~$0.10/hr plus nodes (2x small, e.g. t3.medium), ALB, EBS, NAT gateway. Teardown instructions are mandatory in the README.

## Success criteria
- `docker compose up` gives a working app and all tests pass locally.
- Following the README on a fresh AWS account yields a working HTTPS URL on EKS.
- A merge to main builds, tests, deploys, and passes the smoke test with no stored AWS keys.
