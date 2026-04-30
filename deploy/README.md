# ShopChat — OpenShift Deployment Guide

Replace the placeholders below with your own values before running any commands:

| Placeholder | Description |
|---|---|
| `<YOUR_NAMESPACE>` | OpenShift project/namespace name |
| `<YOUR_CLUSTER>` | OpenShift cluster domain (e.g. `apps.mycluster.com`) |
| `lrangine` | Quay.io organisation (already set) |
| `<YOUR_GCP_PROJECT>` | GCP project ID for Vertex AI |
| `<LANGFUSE_HOST>` | URL of your Langfuse instance |
| `<LANGFUSE_PUBLIC_KEY>` | Langfuse public key |
| `<LANGFUSE_SECRET_KEY>` | Langfuse secret key |

---

## Architecture

```
Browser
  └─► OpenShift Route (HTTPS)
        └─► shop-chat-ui Pod (nginx :8080)
              ├─► static assets  (React SPA)
              └─► /api/* proxy ──► shop-chat-backend Pod (FastAPI :8000)
                                        ├─► MCP server (stdio subprocess, bundled in image)
                                        ├─► CSV data (/app/data, bundled in image)
                                        ├─► Google Vertex AI (Claude Sonnet 4)
                                        └─► Langfuse (already deployed)
```

---

## Prerequisites

- `oc` CLI logged into the cluster
- `helm` v3.x installed
- `podman` or `docker` for building images
- Access to a Quay.io repository (or another registry)

---

## Step 1 — Log in and set your namespace

```bash
oc login --web https://console-openshift-console.<YOUR_CLUSTER>
oc project <YOUR_NAMESPACE>
```

---

## Step 2 — Create the GCP credentials Secret

### Demo (using your local Application Default Credentials)

```bash
# Verify the ADC file exists
ls ~/.config/gcloud/application_default_credentials.json

oc create secret generic gcp-vertex-credentials \
  --from-file=sa-key.json=$HOME/.config/gcloud/application_default_credentials.json \
  -n <YOUR_NAMESPACE>
```

### Production (dedicated service account)

```bash
# 1. Create the service account
gcloud iam service-accounts create shop-chat-vertex \
  --display-name="ShopChat Vertex AI" \
  --project=<YOUR_GCP_PROJECT>

# 2. Grant Vertex AI access
gcloud projects add-iam-policy-binding <YOUR_GCP_PROJECT> \
  --member="serviceAccount:shop-chat-vertex@<YOUR_GCP_PROJECT>.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# 3. Download the key (NEVER commit this file)
gcloud iam service-accounts keys create gcp-sa-key.json \
  --iam-account="shop-chat-vertex@<YOUR_GCP_PROJECT>.iam.gserviceaccount.com"

# 4. Create the OpenShift Secret
oc create secret generic gcp-vertex-credentials \
  --from-file=sa-key.json=./gcp-sa-key.json \
  -n <YOUR_NAMESPACE>

# 5. Remove the local key file
rm gcp-sa-key.json
```

---

## Step 3 — Build and push container images

Run these commands from the **repository root**.

### Log in to Quay.io

```bash
podman login quay.io
```

### Build and push (or use `make docker-release`)

```bash
# Build backend (from repo root)
podman build --platform linux/amd64 \
  -f shop-backend-api/Dockerfile \
  -t quay.io/lrangine/ai-e2e-demo:backend \
  .
podman push quay.io/lrangine/ai-e2e-demo:backend

# Build frontend
podman build --platform linux/amd64 \
  -f shop-ui/Dockerfile \
  -t quay.io/lrangine/ai-e2e-demo:ui \
  shop-ui/
podman push quay.io/lrangine/ai-e2e-demo:ui
```

Or use the Makefile (auto-increments the `VERSION` file after each release):

```bash
# Edit Makefile: set REGISTRY to your quay.io repo first
make docker-release
```

> **Note:** Make sure the repository on quay.io is set to **Public**, or create a
> pull secret — see the optional section below.

---

## Step 4 — Deploy with Helm

Create a local `my-values.yaml` (add to `.gitignore` — never commit credentials):

```yaml
backend:
  image:
    repository: quay.io/lrangine/ai-e2e-demo
    tag: backend

ui:
  image:
    repository: quay.io/lrangine/ai-e2e-demo
    tag: ui

vertexProjectId: "<YOUR_GCP_PROJECT>"

langfuse:
  enabled: true
  host: "<LANGFUSE_HOST>"
  publicKey: "<LANGFUSE_PUBLIC_KEY>"
  secretKey: "<LANGFUSE_SECRET_KEY>"
```

Then install:

```bash
helm install shop-chat deploy/helm/shop-chat/ \
  --namespace <YOUR_NAMESPACE> \
  -f my-values.yaml
```

### Optional: Quay.io pull secret (if repo is private)

```bash
podman login quay.io --username lrangine --authfile /tmp/quay-auth.json

oc create secret generic quay-pull-secret \
  --from-file=.dockerconfigjson=/tmp/quay-auth.json \
  --type=kubernetes.io/dockerconfigjson \
  -n <YOUR_NAMESPACE>

oc secrets link default quay-pull-secret --for=pull -n <YOUR_NAMESPACE>
```

Add to `my-values.yaml`:
```yaml
imagePullSecrets:
  - name: quay-pull-secret
```

---

## Step 5 — Get the app URL

```bash
# Frontend (primary user-facing URL)
oc get route shop-chat-ui -n <YOUR_NAMESPACE>

# Backend API (for direct API access / testing)
oc get route shop-chat-backend -n <YOUR_NAMESPACE>
```

---

## Upgrade

After making changes, run `make docker-release` (builds, pushes, increments `VERSION`), then:

```bash
helm upgrade shop-chat deploy/helm/shop-chat/ \
  --namespace <YOUR_NAMESPACE> \
  -f my-values.yaml \
  --set backend.image.tag=backend-v<N> \
  --set ui.image.tag=ui-v<N>
```

## Uninstall

```bash
helm uninstall shop-chat -n <YOUR_NAMESPACE>

# The GCP credentials secret is not managed by Helm — delete manually if needed
oc delete secret gcp-vertex-credentials -n <YOUR_NAMESPACE>
```

---

## Troubleshooting

### Check Pod status

```bash
oc get pods -n <YOUR_NAMESPACE>
oc describe pod <pod-name> -n <YOUR_NAMESPACE>
```

### View logs

```bash
oc logs -f deployment/shop-chat-backend -n <YOUR_NAMESPACE>
oc logs -f deployment/shop-chat-ui -n <YOUR_NAMESPACE>
```

### Backend health check

```bash
BACKEND_ROUTE=$(oc get route shop-chat-backend -n <YOUR_NAMESPACE> --template='{{ .spec.host }}')
curl https://$BACKEND_ROUTE/health
```

### Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend pod `CrashLoopBackOff` | Missing GCP secret | Check `oc get secret gcp-vertex-credentials` |
| `PERMISSION_DENIED` from Vertex AI | ADC token expired or wrong project | Recreate the GCP credentials secret |
| UI shows blank / network error | `BACKEND_URL` wrong | Check `oc describe deployment shop-chat-ui` → env BACKEND_URL |
| SSE streaming stops mid-response | Proxy timeout | Already handled — nginx `proxy_read_timeout 300s` is set |

---

## Langfuse Self-Hosting Reference

- Official self-hosting docs: https://langfuse.com/docs/deployment/self-host
- Kubernetes / Helm guide: https://langfuse.com/docs/deployment/self-host#kubernetes--helm
