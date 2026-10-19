# NPSH support hub

Versioned resources for the independent NPSHr, Transient and CFD Labs.
The application remains at [npshr.vercel.app](https://npshr.vercel.app/).

## Get the reviewed resources

```sh
git clone --recurse-submodules https://github.com/simcalc/npsh-support.git
cd npsh-support
python -B tools/verify_support.py
python -B tools/worker_preflight.py
```

| Directory | Purpose | Calculation boundary |
| --- | --- | --- |
| [modules/OpenFoam](modules/OpenFoam) | Pinned Foundation 12 worker, tutorials, native checkpoints and numerical benchmark evidence | Fixed educational benchmarks; no exact-pump validation claim |
| [modules/PyAnsys](modules/PyAnsys) | Pinned PyFluent SDK, learning meshes and frozen-rotor development evidence | Client readiness does not establish a licensed Fluent session |
| [catalog/resources.lock.json](catalog/resources.lock.json) | Exact commits, source-manifest hashes and release asset index | GitHub asset digests are recorded only when GitHub supplies them |
| [docs/native-worker.md](docs/native-worker.md) | Local native execution and online worker prerequisites | Native execution is separate from cloud Python calculations |
| [validation](validation) | Empty measurement template and physical validation protocol | No measurements have been invented |

Submodules preserve original repositories, histories, licenses and releases.
Clone with `--recurse-submodules`; use `git submodule update --init` after
pulling a reviewed hub update. `git submodule update --remote` changes the
reviewed version and requires a new assessment. No runtime download occurs
during application calculations.

## Current readiness (19 October 2026)

- Online NPSHr and Transient L1/L2 calculations run in their independent Python
  services. Both CFD workbenches provide input validation and evidence reduction.
- This hub is source/evidence support, not an online solver service.
- The inspected Windows laptop has no WSL/OpenFOAM or native Fluent. Its
  installed PyFluent client alone cannot run CFD.
- Native jobs need a separate bounded worker. No arbitrary user jobs are sent
  to GitHub Actions. Development workflows remain at their original repositories.
- Physical validation awaits measurements with compatible pump configuration,
  operating conditions, units, pressure/datum basis and uncertainty.

The private legacy worker repository `simcalc/npsh-cfd-labs` was recovered at
its original commit `947798a19a5a5a9c85df62cbd77633d747eb1c78`; it is not a
public submodule. Current public educational resources are in OpenFoam.
Local historical export directories remain evidence archives and are not
runtime application dependencies.

No Main source, database, student study, secret, book PDF or screenshot is
copied into this public hub. Solver downloads retain their original notices.
