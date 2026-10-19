"""Inspect the pinned educational worker; never install or start a solver."""
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from verify_support import ROOT, verify


def preflight(root=ROOT):
    source = verify(root)
    if not source['ok']:
        return {**source, 'nativeWorkerReady': False}
    try:
        result = subprocess.run([sys.executable, '-B', str(root / 'modules/OpenFoam/tools/cfd_worker/run.py'), '--capabilities'],
                                cwd=root, capture_output=True, timeout=15, check=True)
        if len(result.stdout) > 65536:
            raise ValueError('oversize capabilities')
        capabilities = json.loads(result.stdout)
        ready = capabilities['adapters']['openfoam']['available'] is True
        return {'schemaVersion': 'untirta.support-worker-preflight.v1', 'ok': True,
                'status': 'ReadyForFixedBenchmark' if ready else 'RuntimeRequired',
                'nativeWorkerReady': ready, 'nativeOnlineJobServiceAvailable': False,
                'reasonCode': capabilities['adapters']['openfoam']['reasonCode'],
                'action': 'Use the bounded Linux runner documented in docs/native-worker.md.' if ready else
                          'Provide Linux/WSL2, pinned Foundation 12 and delegated bounded cgroup v2. Windows client SDK readiness does not supply a native solver.',
                'capabilities': capabilities, 'solverExecuted': False, 'experimentalValidation': False}
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
        return {'ok': False, 'status': 'ReviewRequired', 'nativeWorkerReady': False,
                'reasonCode': 'SUPPORT_WORKER_INSPECTION_UNAVAILABLE',
                'action': 'Check the pinned worker and Python environment; no solver fallback was started.', 'solverExecuted': False}


if __name__ == '__main__':
    result = preflight()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get('nativeWorkerReady') else 2)
