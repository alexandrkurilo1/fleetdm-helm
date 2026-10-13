# FleetDM on Kubernetes (Helm + kind)

A Helm chart that deploys [FleetDM](https://fleetdm.com) together with MySQL and Redis, plus a Makefile that
spins it up on a local [kind](https://kind.sigs.k8s.io) cluster.

| Component | Kind | Image | Notes |
|-----------|------|-------|-------|
| Fleet server | Deployment + NodePort Service | `fleetdm/fleet:v4.93.0` | Terminates TLS itself, `/healthz` probes |
| DB migrations | Job (`<release>-migrate-<revision>`) | `fleetdm/fleet:v4.93.0` | Runs `fleet prepare db --no-prompt` on every install/upgrade |
| MySQL | StatefulSet + PVC | `mysql:8.0.43` | Random credentials in a Secret, kept across upgrades |
| Redis | StatefulSet + PVC | `redis:7.4.5-alpine` | AOF persistence, non-root |

```
repo
├── charts/fleet/          # the Helm chart
├── hack/kind-config.yaml  # kind cluster: NodePort 30443 -> host :8443
├── hack/verify.sh         # end-to-end checks used by `make verify`
├── .github/workflows/     # CI: lint/test on PRs, release on main
├── docs/                  # theoretical part (architecture document + HLD)
└── Makefile
```

## Prerequisites

Docker (Docker Desktop, OrbStack or Colima), `kind` ≥ 0.24, `kubectl`, `helm` ≥ 3.14, `curl`.

```bash
brew install kind kubectl helm   # macOS
```

## Install

```bash
make cluster    # create the kind cluster "fleet"
make install    # helm upgrade --install, waits for MySQL, Redis, migrations and Fleet
```

`make install` is idempotent; running it again performs a `helm upgrade` (and a new migration Job, which only applies
new migrations). Pass extra Helm flags with `HELM_ARGS`, e.g. `make install HELM_ARGS="--set fleet.replicaCount=2"`.

Open **https://localhost:8443** and complete the Fleet setup wizard (first admin user). The certificate is self-signed;
either accept the browser warning or trust the CA exported by `make ca`.

### Using the published chart instead of the local copy

```bash
helm repo add fleet-local https://alexandrkurilo1.github.io/fleetdm-helm
helm install fleet fleet-local/fleet -n fleet --create-namespace --wait --wait-for-jobs
# or, from the OCI registry
helm install fleet oci://ghcr.io/alexandrkurilo1/charts/fleet --version 0.1.0 -n fleet --create-namespace
```

## Teardown

```bash
make uninstall       # helm uninstall + delete PVCs + delete namespace
make cluster-delete  # optional: remove the kind cluster itself
```

## Verification

One command runs every check below:

```bash
make verify
```

```
  ✔ MySQL StatefulSet ready
  ✔ Redis StatefulSet ready
  ✔ Fleet Deployment ready
  ✔ Migration job.batch/fleet-migrate-1 succeeded
  ✔ MySQL: Fleet schema present (… tables)
  ✔ Redis: PING -> PONG
  ✔ Fleet /healthz via https://localhost:8443 -> 200 (TLS verified)
  ✔ Agent enroll endpoint reachable (HTTP 401 without enroll secret, as expected)
All checks passed.
```

The same checks manually:

```bash
# 1. All pods Running/Ready, migration Job Completed
kubectl -n fleet get pods,jobs

# 2. Migrations ran (fleet prepare db) — output ends with "Migrations completed."
kubectl -n fleet logs job/fleet-migrate-1 -c prepare-db

# 3. MySQL is up and holds the Fleet schema
kubectl -n fleet exec statefulset/fleet-mysql -- sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SHOW TABLES" | head'

# 4. Redis answers
kubectl -n fleet exec statefulset/fleet-redis -- redis-cli ping      # PONG

# 5. Fleet is healthy; /healthz returns 200 only when MySQL and Redis are both reachable
make ca && curl --cacert fleet-ca.crt https://localhost:8443/healthz -w '%{http_code}\n'

# 6. In-cluster probe packaged with the chart
make test   # helm test
```

## Exposing Fleet and enrolling agents

The kind node maps NodePort `30443` to port `8443` on every host interface, and Fleet serves HTTPS directly, so the UI
and the agent API (`/api/v1/osquery/*`, `/api/fleet/orbit/*`) are reachable from the host and from other machines on
the LAN. `make install` adds the host's LAN IP (`HOST_IP`, auto-detected) to the certificate's SANs. The generated
certificate covers:

* `localhost`, `127.0.0.1`, `fleet.local`, `host.docker.internal`, the LAN IP
* the in-cluster names `fleet`, `fleet.fleet.svc`, `fleet.fleet.svc.cluster.local`

To enroll a host:

1. In the UI, go to **Hosts → Add hosts** and copy the enroll secret.
2. Export the CA: `make ca`.
3. Build an agent package with [`fleetctl`](https://fleetdm.com/docs/using-fleet/fleetctl-cli) (`npm i -g fleetctl`):

   ```bash
   fleetctl package --type=pkg \
     --fleet-url=https://<HOST_IP>:8443 \
     --enroll-secret=<secret> \
     --fleet-certificate=fleet-ca.crt
   ```

   Use `--type=deb|rpm|msi` for other platforms. Install the package on the target machine; it appears under **Hosts**
   within a minute.

The certificate is generated once and reused on upgrades so enrolled agents keep trusting it. To change the SANs later,
delete the secret (`kubectl -n fleet delete secret fleet-tls`) and run `make install` again, or supply your own
certificate with `--set fleet.tls.existingSecret=<tls-secret>`.

On a cluster with an ingress controller, `--set fleet.ingress.enabled=true,fleet.ingress.host=fleet.example.com` adds an
Ingress that proxies to Fleet over HTTPS.

## How `fleet prepare db` runs automatically

`templates/job-migration.yaml` is a regular Job, not a Helm hook. With the bundled MySQL, a `pre-install` hook would
run before the database exists, and a `post-install` hook would deadlock `helm --wait`, because Fleet only reports
ready once the schema exists. Instead:

1. The Job and the Fleet pod both start with a `wait-for-mysql` init container (`mysqladmin ping` with the Fleet credentials).
2. The Job runs `fleet prepare db --no-prompt`. The command is idempotent: on a fresh install it creates the schema; on an upgrade it applies only new migrations.
3. Fleet's startup probe on `/healthz` holds the pod un-ready (and restarts it if needed) until the migrations are in place.
4. The release revision is part of the Job name, so each `helm upgrade` creates a fresh Job. Completed Jobs are cleaned up by `ttlSecondsAfterFinished`.

`make install` uses `--wait --wait-for-jobs`, so it returns only after the migration Job has succeeded and Fleet is ready.

## Configuration

Commonly changed values (see [values.yaml](charts/fleet/values.yaml) for all of them):

| Value | Default | Description |
|-------|---------|-------------|
| `fleet.image.tag` | chart `appVersion` | Fleet version |
| `fleet.replicaCount` | `1` | Fleet server replicas (stateless; MySQL/Redis hold state) |
| `fleet.service.type` / `nodePort` | `NodePort` / `30443` | How Fleet is exposed |
| `fleet.tls.enabled` | `true` | Fleet serves HTTPS itself (osquery agents require TLS) |
| `fleet.tls.dnsNames` / `ipAddresses` | see file | SANs of the generated certificate |
| `fleet.tls.existingSecret` | `""` | Use your own `kubernetes.io/tls` secret |
| `fleet.migrations.enabled` | `true` | Run `fleet prepare db` on install/upgrade |
| `fleet.extraEnv` | `[]` | Any [Fleet server setting](https://fleetdm.com/docs/configuration/fleet-server-configuration) as `FLEET_*` env vars |
| `fleet.ingress.enabled` | `false` | Optional Ingress |
| `mysql.enabled` / `redis.enabled` | `true` | Set to `false` and fill `externalMysql.*` / `externalRedis.address` to use managed services |
| `mysql.auth.password` | random | Generated once and persisted across upgrades |
| `*.persistence.enabled` / `size` | `true` / 5Gi, 1Gi | PVCs for MySQL and Redis |

## CI/CD

* **[lint-test.yaml](.github/workflows/lint-test.yaml)** runs on PRs and on pushes to `main`. It runs `ct lint` (which
  also requires a `version` bump in `Chart.yaml` whenever the chart changes) and validates the rendered manifests with
  kubeconform against Kubernetes 1.31. It then creates a kind cluster and runs `ct install`, which installs the chart
  with [ci/ci-values.yaml](charts/fleet/ci/ci-values.yaml), waits for readiness and runs `helm test`.
* **[release.yaml](.github/workflows/release.yaml)** runs on pushes to `main` that touch `charts/`.
  [chart-releaser](https://github.com/helm/chart-releaser-action) packages every chart version that hasn't been
  released yet. It creates a GitHub Release (`fleet-<version>`) with the `.tgz` and updates `index.yaml` on the
  `gh-pages` branch, which is the public Helm repo. The same package is also pushed to GHCR as an OCI artifact.

To release a new version: change the chart, bump `version` in `Chart.yaml` (and `appVersion` for a new Fleet), and merge
to `main`.

One-time repo setup: create an empty `gh-pages` branch and enable GitHub Pages from it (Settings → Pages), and allow
Actions to write (Settings → Actions → Workflow permissions → Read and write).

## Theoretical part

The architecture design document for "Company Inc." is in [docs/](docs/). It includes the PDF, its source, and the
high-level diagram as a draw.io file and an SVG.
