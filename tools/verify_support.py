"""Read-only pinned source verification. No network, install or solver launch."""
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'modules/OpenFoam': 'simcalc/OpenFoam', 'modules/PyAnsys': 'simcalc/PyAnsys'}


def git(path, *arguments):
    return subprocess.check_output(['git', '-C', str(path), *arguments], timeout=15, stderr=subprocess.DEVNULL, text=True).strip()


def verify(root=ROOT, manifest=None):
    try:
        if manifest is None:
            manifest = json.loads((root / 'catalog/resources.lock.json').read_text(encoding='utf-8'))
        if manifest.get('schemaVersion') != 'untirta.support-resources.v1':
            raise ValueError('schema')
        entries = manifest['modules']
        if len(entries) != 2 or {entry['path'] for entry in entries} != set(MODULES):
            raise ValueError('modules')
        issues = []
        for entry in entries:
            path = entry['path']
            if entry['repository'] != MODULES[path] or not re.fullmatch('[0-9a-f]{40}', entry['commit']):
                raise ValueError('identity')
            module = root / path
            if module.is_symlink() or module.resolve() != root.resolve().joinpath(path):
                raise ValueError('path')
            if git(root, 'ls-files', '--stage', '--', path).split()[:2] != ['160000', entry['commit']]:
                issues.append({'module': path, 'reasonCode': 'SUPPORT_GITLINK_MISMATCH'})
            if git(module, 'rev-parse', 'HEAD') != entry['commit']:
                issues.append({'module': path, 'reasonCode': 'SUPPORT_COMMIT_MISMATCH'})
            if git(module, 'remote', 'get-url', 'origin').removesuffix('.git') != 'https://github.com/' + MODULES[path]:
                issues.append({'module': path, 'reasonCode': 'SUPPORT_REMOTE_MISMATCH'})
            if git(module, 'status', '--porcelain', '--untracked-files=all'):
                issues.append({'module': path, 'reasonCode': 'SUPPORT_MODULE_MODIFIED'})
            for item in entry['sourceFiles']:
                source = module / item['path']
                if item['path'] not in {'README.md', 'release-manifest.json', 'requirements.txt'}:
                    raise ValueError('source path')
                # These allowlisted text files use canonical Git LF bytes;
                # a Windows CRLF checkout must match the same Linux manifest.
                blob = subprocess.check_output(['git', '-C', str(module), 'show', entry['commit'] + ':' + item['path']], timeout=15, stderr=subprocess.DEVNULL)
                if (source.is_symlink() or sha256(blob).hexdigest() != item['sha256']
                        or source.read_bytes().replace(b'\r\n', b'\n') != blob):
                    issues.append({'module': path, 'reasonCode': 'SUPPORT_SOURCE_HASH_MISMATCH'})
        return {'ok': not issues, 'status': 'Verified' if not issues else 'ReviewRequired', 'diagnostics': issues,
                'solverExecuted': False, 'experimentalValidation': False}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return {'ok': False, 'status': 'ReviewRequired', 'reasonCode': 'SUPPORT_SOURCE_UNAVAILABLE',
                'action': 'Restore the reviewed manifest and run git submodule update --init. Do not replace the pinned commits silently.',
                'solverExecuted': False, 'experimentalValidation': False}


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ok'] else 2)
