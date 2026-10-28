# Notes API on Kubernetes with GitOps (Helm + Argo CD + Kustomize)

A small FastAPI notes app (create, list, filter by tag, get, delete) deployed
the Kubernetes way: plain manifests, a Helm chart, Kustomize overlays for
dev/prod, and Argo CD Applications that sync the cluster from this repo.
Git is the source of truth — change a value here, Argo CD applies it.

> **No Docker daemon, Helm, kubectl, or cluster is available in the author's
> sandbox**, so the image is built in GitHub Actions CI, not locally, and
> no cluster is created by this repository alone. Deploy only when you
> choose to, on your own cluster.

## Features

- `GET /` — service info; `GET /health` — liveness/readiness probe
- `GET /api/notes`, `POST /api/notes`, `GET /api/notes/{id}`,
  `DELETE /api/notes/{id}` — notes (in-memory, filterable by `?tag=`)
- `GET /metrics` — Prometheus metrics (`notes_created_total`, `notes_total`)
- Pydantic validation: empty titles are rejected with HTTP 422
- Non-root container user, `HEALTHCHECK`, pinned Python dependencies

## Architecture

```
GitHub Actions CI (pytest, Trivy, Helm lint + template render,
                   manifest validation, Docker build)
        |
        v
This repo (source of truth)
   |-- helm/notes-api          -> Argo CD Application notes-api-prod
   |-- k8s/overlays/dev        -> Argo CD Application notes-api-dev
   |-- k8s/base + overlays     -> kubectl apply -k (manual path)
        |
        v
Kubernetes cluster: Deployment (2-3 replicas) + Service + Ingress
                    + HPA (2-5, CPU 70%) + ServiceMonitor for Prometheus
```

## Technologies

| Piece | Choice | Why |
|---|---|---|
| App | FastAPI + Uvicorn | Small, typed, fast to test |
| Container | Docker + Compose | One command to run anywhere |
| Orchestration | Kubernetes | Replicas, probes, HPA, rolling updates |
| Packaging | Helm chart | One install, values per environment |
| Overlays | Kustomize | Dev (1 replica, debug) vs prod (3 replicas) without forks |
| GitOps | Argo CD | Automated sync, prune, self-heal from git |
| CI | GitHub Actions | Tests, Trivy scan, Helm lint/render, manifest validation, image build |
| Metrics | Prometheus client + ServiceMonitor | Standard `/metrics` endpoint |

## Run locally (no cluster needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
pip install pytest==9.0.3 httpx==0.28.1
python -m pytest tests/ -q
uvicorn app.main:app --port 8000
# or: docker compose up --build   (needs a Docker daemon)
```

## Deploy to Kubernetes (your cluster, your decision)

```bash
# Fastest: Helm (change the image + host in values first)
helm install notes-api helm/notes-api --namespace notes-api --create-namespace

# Or plain manifests with Kustomize
kubectl apply -k k8s/overlays/prod

# Or GitOps: install Argo CD first, then apply the Applications
kubectl apply -f gitops/argocd-application.yaml
kubectl apply -f gitops/argocd-application-dev.yaml

# Check it
kubectl get pods -l app=notes-api -n notes-api
kubectl port-forward svc/notes-api 8000:80 -n notes-api
curl http://localhost:8000/health
```

Before applying, change two placeholders to your own values: the image
(`notes-api:latest` in `k8s/base/deployment.yaml` and `helm/notes-api/values.yaml`)
and the Ingress host (`notes.example.com`).

## Testing

- `tests/test_main.py`: root, health, create/get/list/filter, delete, 404,
  validation (422), metrics — run with `python -m pytest tests/ -q`.
- CI additionally runs Trivy, `helm lint` + `helm template` render check,
  YAML validation of the plain manifests and GitOps files, and a Docker
  image build (no push).

## Security

- Non-root container and pod, dropped capabilities, no privilege escalation.
- No secrets in git: there are no credentials in this repo at all — the
  ConfigMap holds only non-sensitive settings, and no Secret object is
  committed. Add a real Secret from your own secret manager if you add a
  database later.
- CI scans the tree with Trivy (HIGH/CRITICAL, unfixed ignored) and fails
  on findings.
- Ingress is HTTP in this demo — add TLS (cert-manager + Let's Encrypt)
  before exposing it beyond a demo.

## Limitations (honest)

- Notes are in-memory: a pod restart clears them. For real use, add a
  database (PostgreSQL with a StatefulSet or a managed database) behind
  the API.
- HTTP only — add a TLS Issuer before real traffic.
- No image registry publish step in CI: build your image and push it to
  your own registry, then point the chart/values at it.
