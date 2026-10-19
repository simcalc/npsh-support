#!/usr/bin/env bash
# Explicit provisioning for a Codespace or the reviewed development workflow.
set -euo pipefail
case "${1:-}" in
  codespaces) [[ "${CODESPACES:-}" == true ]] ;;
  actions)
    [[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY:-}" == simcalc/npsh-support ]]
    python3 -B tools/github_cfd_workflow.py validate
    ;;
  *) echo 'Select the explicit codespaces or actions provisioning scope.' >&2; exit 2 ;;
esac
[[ "$(uname -m)" == x86_64 ]]
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]]
if [[ "$(dpkg-query --show --showformat='${db:Status-Status} ${Version}' openfoam12 2>/dev/null || true)" == 'installed 20250206' ]]; then
  echo 'Pinned OpenFOAM 12 package already installed.'
  exit 0
fi
package_dir="$(mktemp -d)"
trap 'rm -f -- "$package_dir/openfoam12_20250206_amd64.deb"; rmdir -- "$package_dir"' EXIT
package_path="$package_dir/openfoam12_20250206_amd64.deb"
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --retry 2 --max-time 300 --max-filesize 112877506 \
  'https://github.com/simcalc/OpenFoam/releases/download/openfoam12-20250206/openfoam12_20250206_amd64.deb' \
  --output "$package_path"
[[ "$(stat -c %s "$package_path")" == 112877506 ]]
printf '%s  %s\n' 'b3dcd9a636a5a827bf43ffcf0156922ba6db492123f035eae1046ee759602dd1' "$package_path" | sha256sum --check --strict
chmod 755 "$package_dir"
chmod 644 "$package_path"
sudo timeout 300 apt-get update -q
sudo timeout 300 apt-get install --no-install-recommends -y "$package_path"
[[ "$(dpkg-query --show --showformat='${db:Status-Status} ${Version}' openfoam12)" == 'installed 20250206' ]]
