#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY:-}" == simcalc/npsh-support ]]
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]]
case "${CFD_CASE_PROFILE:-}" in
  transient-cavity-v1|cavitation-bullet-v1) ;;
  *) echo 'Only reviewed fixed development fixtures may run.' >&2; exit 2 ;;
esac
python3 -B tools/verify_support.py
# Vendor environment probes use optional failing commands. Check its final
# status explicitly, then restore strict mode before starting any solver.
set +eu
source /opt/openfoam12/etc/bashrc
foam_environment_status=$?
set -euo pipefail
(( foam_environment_status == 0 ))
[[ "${WM_PROJECT_VERSION:-}" == 12 ]]
mkdir -p outputs/native
python_path="$(command -v python3)"
foam_library_path="${LD_LIBRARY_PATH:-}"
[[ -n "$foam_library_path" && ${#foam_library_path} -le 32768 && "$foam_library_path" != *$'\n'* && "$foam_library_path" != *$'\r'* ]]
sudo --preserve-env=PATH,LD_LIBRARY_PATH,WM_PROJECT_VERSION,WM_PROJECT_DIR,FOAM_LIBBIN,FOAM_APPBIN,FOAM_ETC \
  systemd-run --scope --unit="untirta-development-${GITHUB_RUN_ID}" \
  -p Delegate=yes -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=32 \
  /usr/bin/env "LD_LIBRARY_PATH=$foam_library_path" \
  "$python_path" -B modules/OpenFoam/tools/cfd_worker/run.py \
  --benchmark "$CFD_CASE_PROFILE" --workspace "$PWD/outputs/native" --report "$PWD/outputs/native-report.json"
