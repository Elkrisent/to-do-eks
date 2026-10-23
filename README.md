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

---

# Deploying to EKS

> **Cost warning.** From Stage 3 you are billed until you tear down (see "Teardown" at the bottom):
> EKS control plane ~$0.10/h, 2x t3.medium nodes, a NAT gateway, an ALB and an EBS volume.
> Roughly $5-6/day. Tear down when you stop for the day.

Commands are meant to be run in one terminal session, since they rely on exported variables.
Steps marked **MANUAL** are things only you can do (or that should never be automated), with the reason.

## Stage 2: AWS prerequisites

**Needs:** `aws`, `eksctl`, `kubectl`, `helm`, and the CLI logged in as an IAM user (not root).

```bash
aws sts get-caller-identity          # Arn must end in user/<you>, NOT root
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

**ECR** is AWS's private image registry. EKS nodes pull your images from it. Create one repo per image:

```bash
for r in todo-backend todo-frontend; do
  aws ecr create-repository --repository-name $r --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability IMMUTABLE        # a tag can never be overwritten, so a tag always means the same image
done
```
`IMMUTABLE` means you must use a new tag for every push (we use the git SHA). Cheap housekeeping so old images don't pile up:

```bash
for r in todo-backend todo-frontend; do
  aws ecr put-lifecycle-policy --repository-name $r --region $AWS_REGION --lifecycle-policy-text \
   '{"rules":[{"rulePriority":1,"description":"keep last 10","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":10},"action":{"type":"expire"}}]}'
done
```

## Stage 3: the cluster (billing starts)

`eks/cluster.yaml` describes the cluster; **eksctl** turns it into a CloudFormation stack that creates the VPC, subnets,
NAT gateway, EKS control plane, IAM roles, add-ons (including the EBS driver Postgres needs) and the worker nodes.

```bash
eksctl create cluster -f eks/cluster.yaml     # ~15-20 minutes
aws eks update-kubeconfig --name todo-eks --region $AWS_REGION   # points kubectl at the new cluster
kubectl get nodes                              # expect 2 nodes, STATUS Ready
```
**MANUAL:** you run this yourself because it starts billing. `update-kubeconfig` writes the cluster address and an
auth recipe into `~/.kube/config`; every later `kubectl` command uses it.

## Stage 4: the AWS Load Balancer Controller

An `Ingress` is only a routing rule. This controller watches for Ingresses and creates the real ALB in AWS.
It needs permission to call AWS APIs, which it gets through **EKS Pod Identity**: an IAM role linked to its Kubernetes service account.

```bash
LBC_VERSION=v3.6.1
# 1. The IAM permissions the controller needs (a policy AWS publishes with the controller)
curl -so /tmp/lbc-iam-policy.json \
  https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/$LBC_VERSION/docs/install/iam_policy.json
aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file:///tmp/lbc-iam-policy.json

# 2. An IAM role with that policy, linked to the controller's service account
eksctl create podidentityassociation --cluster todo-eks --region $AWS_REGION \
  --namespace kube-system --service-account-name aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --permission-policy-arns arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy

# 3. Install the controller. region/vpcId are passed explicitly because the controller
#    can't always auto-detect them from inside a pod.
VPC_ID=$(aws eks describe-cluster --name todo-eks --region $AWS_REGION --query cluster.resourcesVpcConfig.vpcId --output text)
helm repo add eks https://aws.github.io/eks-charts && helm repo update eks
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system \
  --version 3.6.1 \
  --set clusterName=todo-eks --set region=$AWS_REGION --set vpcId=$VPC_ID \
  --set serviceAccount.create=true --set serviceAccount.name=aws-load-balancer-controller

kubectl -n kube-system rollout status deploy/aws-load-balancer-controller
```
The IAM steps are one-time setup that **creates permissions**, so they are deliberately manual and worth reading.

## Stage 5: first deploy, by hand

```bash
# Build and push both images. Tags are immutable, so use a fresh tag each time.
export IMAGE_TAG=$(git rev-parse --short HEAD)
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
for c in backend frontend; do
  docker build -t $ECR_REGISTRY/todo-$c:$IMAGE_TAG $c
  docker push $ECR_REGISTRY/todo-$c:$IMAGE_TAG
done

# MANUAL: create the database Secret. It is made by hand so the password never lives in git.
kubectl apply -f k8s/00-namespace.yaml
PGPASS=$(openssl rand -hex 16)
kubectl -n todo create secret generic todo-db \
  --from-literal=POSTGRES_USER=todo --from-literal=POSTGRES_PASSWORD="$PGPASS" --from-literal=POSTGRES_DB=todo \
  --from-literal=DATABASE_URL="postgresql+psycopg://todo:${PGPASS}@postgres:5432/todo"

# Apply everything. envsubst fills ${ECR_REGISTRY} and ${IMAGE_TAG} into the manifests.
for f in k8s/0*.yaml; do envsubst '${ECR_REGISTRY} ${IMAGE_TAG}' < "$f" | kubectl apply -f -; done

kubectl -n todo get pods -w            # wait for all Running/Ready (Postgres first, then backend)
kubectl -n todo get ingress todo       # ADDRESS appears after 2-3 min: the ALB's DNS name
curl http://<ADDRESS>/api/healthz      # expect {"status":"ok"}; open http://<ADDRESS>/ in a browser
```
If the ALB isn't created, check the controller: `kubectl -n kube-system logs deploy/aws-load-balancer-controller`.

At this point the app is live on the internet over plain HTTP. HTTPS comes in the CloudFront stage.

## Teardown (do this when you stop, or you keep paying)

Order matters: the ALB and EBS volume were created by Kubernetes controllers, **outside** the CloudFormation stack.
If you delete the cluster first, they can be left behind (and keep billing) or block the VPC from deleting.

```bash
kubectl delete ingress todo -n todo            # makes the controller delete the ALB
kubectl delete pvc -n todo --all               # deletes the EBS volume (reclaimPolicy: Delete)
kubectl delete namespace todo
helm uninstall aws-load-balancer-controller -n kube-system
eksctl delete cluster -f eks/cluster.yaml --wait   # ~10-15 min
# Optional cleanup of the rest:
aws ecr delete-repository --repository-name todo-backend --force --region $AWS_REGION
aws ecr delete-repository --repository-name todo-frontend --force --region $AWS_REGION
aws iam delete-policy --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy
```
Afterwards, check the console (EC2 -> Load Balancers and Volumes) that nothing is left.

## Coming next
CloudFront + HTTPS lockdown, and the deploy workflow with OIDC, are added in the following stages.
