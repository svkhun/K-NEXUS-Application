# Deploy the prototype to Render

This repository contains a Docker Web Service Blueprint. It builds React in a Node 22 stage and runs the Python API plus built assets in a non-root Python 3.13 image.

## Render setup

1. In Render, choose **New → Blueprint** and connect `svkhun/k-web-application` on `main`.
2. Review `render.yaml`. It requests **Starter compute in Singapore** for continuous operation. Render will charge for the compute plan only when you create the service; importing this repository does not create a service by itself. Check the current [Render pricing](https://render.com/pricing) before confirming.
3. Apply the Blueprint. Render generates `DEMO_SESSION_SECRET` and supplies `RENDER_EXTERNAL_URL`; no secret belongs in Git.
4. Wait for the repository's **Verify prototype** workflow and the deployment to succeed. `autoDeployTrigger: checksPass` gates later deployments on CI.
5. Open the URL shown in Render, and check `/api/v2/health`. Try an auto-save, recall and the three TrustGraph scenarios. In another browser or private window, confirm balances are independent.

For manual Web Service setup, choose **Docker**, repository root, `Dockerfile`, health path `/api/v2/health`, `ENVIRONMENT=production`, `HOST=0.0.0.0`, and a randomly generated `DEMO_SESSION_SECRET` of at least 32 characters. `run.py` binds to Render's `PORT`. Keep exactly one instance and one worker.

Official references: [Docker services](https://render.com/docs/docker), [Blueprint fields](https://render.com/docs/blueprint-spec), [port binding and HTTPS](https://render.com/docs/web-services).

## Domains and sessions

Render terminates HTTPS at its load balancer. Production cookies use `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and the `__Host-` prefix. The app uses an exact origin allowlist, never wildcard credentialed CORS.

If you later configure a custom domain, set `PUBLIC_ORIGIN=https://your-domain.example` in Render. This becomes the canonical API origin; use that domain consistently. The origin must contain only scheme and hostname (and optional port), with no path.

## Capacity and storage

This is an anonymous synthetic-data demo. Each visitor has an independent, server-held session with three preset accounts. Sessions last one hour, are limited to 200 active visitors, and reset after expiry, process restart or deployment. The app rate-limits session creation and API calls and accepts request bodies up to 8 KiB.

Do not increase worker or instance counts while state is in process memory. Multiple workers would have separate session stores. To retain sessions or scale out, move state, idempotency and locks to a shared database/store first. No real account data or biometric authentication is implemented.

## Container verification

```sh
docker build -t k-flow-lab .
docker run --rm -p 8000:10000 k-flow-lab
```

For the local container example, the production environment is deliberately omitted so HTTP cookies work on localhost. Production validation happens in CI with the production environment enabled. CI also audits dependencies and runs the HTTP security tests.
