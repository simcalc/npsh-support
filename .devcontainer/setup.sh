#!/usr/bin/env bash
set -euo pipefail
[[ "${CODESPACES:-}" == true ]]
git submodule update --init --recursive
python3 -B tools/verify_support.py
bash tools/install_openfoam12.sh codespaces
python3 -B -m unittest discover -s tests -v
echo 'Development environment prepared. Native execution still requires a bounded, delegated cgroup.'
echo 'Use the reviewed Actions development job for bounded native verification.'
