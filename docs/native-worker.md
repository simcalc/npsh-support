# Native worker deployment boundary

## What is available

The pinned OpenFoam module contains actual versioned adapters, resource
enforcement, cancellation, immutable native checkpoints and bounded artifact
export. Its public CLI accepts only fixed educational profiles. Main and the
independent Labs retain their Python numerical authority.

Run `python -B tools/worker_preflight.py` to inspect readiness. Exit 2 with
`RuntimeRequired` is an unmet native prerequisite, not a failed Main calculation.
It performs no install, network request, privileged action or CFD execution.

## Free local execution

1. On Windows, installing WSL2 requires an administrator and may require a
   Windows restart. Keep Ubuntu 24.04 separate from Main's Python environment.
   Installation and restart require the machine owner's coordination.
2. Install the exact Foundation 12 `20250206` package after verifying SHA-256
   `b3dcd9a636a5a827bf43ffcf0156922ba6db492123f035eae1046ee759602dd1`.
   The original package/source/license are indexed in the resource catalog.
   The module's GitHub-only installer refuses local machines; do not bypass it.
3. In Linux, source `/opt/openfoam12/etc/bashrc`. The supervisor must inherit a
   delegated cgroup v2 with `MemoryMax=2147483648`, `MemorySwapMax=0`,
   `CPUQuota=100%`, `TasksMax=32` and working `cgroup.kill`. Supply the group's
   required delegation/ownership without running arbitrary student code as root.
4. Verify source pins before running the worker. A reviewed administrator can
   establish the bounded systemd scope, then run the fixed CLI below inside it:

```sh
python3 -B tools/worker_preflight.py
cd modules/OpenFoam
python3 -B tools/cfd_worker/run.py --benchmark transient-cavity-v1 \
  --workspace ../../outputs/native-worker --report ../../outputs/cavity-report.json
```

Use one common workspace root per worker. The worker rejects unavailable
resource enforcement. The disk watchdog is not a filesystem hard quota.
Create `cancel.request` only in the active job directory to cancel it.
Native Linux execution and resource acceptance have not been run on the
inspected Windows laptop, which currently has no WSL installation.

Fluent remains optional. PyFluent 0.42.2 is a client SDK; native Fluent,
compatible runtime, a legitimate licensed session, exact reviewed case,
geometry/zones and native acceptance are separate prerequisites.

## Online job service: acceptance before enabling Run

An online native Run button needs a separate persistent worker service. A
Vercel request function is not that service. The following are deployment
acceptance requirements; this hub does not claim they are installed:

- Authenticated per-owner jobs, exact allowed origin, authorization on every
  status/cancel/download, no tokens in query strings or repository files.
- Bounded queue and one solver job per worker; job IDs/revisions and source
  hashes bind requests to immutable inputs and references.
- Reviewed profile and geometry allowlists, no browser-supplied command,
  executable path, shell fragment, arbitrary script or solver dictionary hook.
- CPU/RAM/process/time/disk enforcement and cancellation of the entire child
  tree, with verified cleanup, finite status deadlines and bounded logs.
- Durable separate artifact storage, verified native receipts, resumable job
  status after restart, retention/quota control and no Main database writes.
- Negative tests for unauthorized access, replay, tampering, wrong revision,
  overload, disconnect, worker loss and artifact integrity.
- No automatic paid fallback, arbitrary GitHub Actions jobs, or public Fluent
  gRPC. Online native Run stays unavailable until a host and these gates exist.

The free path currently selected is a dedicated local student worker. Public
internet exposure, a tunnel or an additional compute service has not been
configured. It requires a separately reviewed deployment choice.

## Sources

- [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install)
- [OpenFOAM Foundation 12 Ubuntu installation](https://openfoam.org/download/12-ubuntu/)
- [Vercel function limits](https://vercel.com/docs/functions/limitations)
- [Git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
