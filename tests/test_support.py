from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'tools'))
from verify_support import verify
from worker_preflight import preflight


class SupportTests(unittest.TestCase):
    def test_actual_checkout_matches_gitlinks_and_source_manifests(self):
        self.assertTrue(verify()['ok'], verify())

    def test_invalid_manifest_cannot_execute_an_arbitrary_module(self):
        manifest = json.loads((ROOT / 'catalog/resources.lock.json').read_text(encoding='utf-8'))
        for key, value in [('path', '../outside'), ('repository', 'other/repository'), ('commit', 'main')]:
            modified = deepcopy(manifest)
            modified['modules'][0][key] = value
            self.assertFalse(verify(manifest=modified)['ok'])

    def test_bad_source_does_not_invoke_worker(self):
        with patch('worker_preflight.verify', return_value={'ok': False, 'reasonCode': 'SUPPORT_COMMIT_MISMATCH'}), patch('worker_preflight.subprocess.run') as run:
            self.assertFalse(preflight()['nativeWorkerReady'])
            run.assert_not_called()

    def test_missing_solver_does_not_claim_native_or_physical_execution(self):
        capabilities = {'adapters': {'openfoam': {'available': False, 'reasonCode': 'CFD_SOLVER_UNAVAILABLE'}}}
        with patch('worker_preflight.verify', return_value={'ok': True}), patch('worker_preflight.subprocess.run') as run:
            run.return_value.stdout = json.dumps(capabilities).encode()
            result = preflight()
        self.assertEqual(result['status'], 'RuntimeRequired')
        self.assertFalse(result['nativeWorkerReady'])
        self.assertFalse(result['nativeOnlineJobServiceAvailable'])
        self.assertFalse(result['solverExecuted'])
        self.assertFalse(result['experimentalValidation'])


if __name__ == '__main__':
    unittest.main()
