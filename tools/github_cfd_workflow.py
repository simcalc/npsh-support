"""Actions-only fixture binding and result packaging; never a solver substitute."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess

from github_cfd_job import Diagnostic, OPENFOAM_COMMIT, REPOSITORY, Request, finite_json, require, verified_report
from verify_support import ROOT, verify


def validate_environment():
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
            "GITHUB_CFD_DEVELOPMENT_SCOPE_REQUIRED", "Run this reviewed manual development workflow in the public support repository.")
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    require(event_path.is_file() and event_path.stat().st_size <= 65536)
    event = finite_json(event_path.read_bytes(), 65536)
    require(event.get("repository", {}).get("private") is False
            and event.get("repository", {}).get("full_name") == REPOSITORY)
    request = Request(os.environ.get("CFD_REQUEST_ID", ""), os.environ.get("CFD_CASE_PROFILE", ""), os.environ.get("GITHUB_SHA", ""))
    require(event.get("inputs") == {"request_id": request.requestId, "case_profile": request.caseProfile})
    require(verify()["ok"], "GITHUB_CFD_SOURCE_UNVERIFIED", "Restore the pinned submodules and resource manifest before running a solver.")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=15, text=True).strip()
    require(commit == request.sourceCommit)
    return request


def pack(request, report):
    verified_report(request, report)
    return {"schemaVersion": "untirta.github-cfd-result.v1", **asdict(request),
            "openfoamCommit": OPENFOAM_COMMIT, "report": report}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "pack"))
    args = parser.parse_args()
    try:
        request = validate_environment()
        output = ROOT / "outputs"
        output.mkdir(exist_ok=True)
        if args.operation == "validate":
            target, value = output / "request.json", asdict(request)
        else:
            raw = output / "native-report.json"
            require(raw.is_file() and raw.stat().st_size <= 60000)
            report = finite_json(raw.read_bytes(), 60000)
            target, value = output / "result.json", pack(request, report)
        encoded = json.dumps(value, indent=2, allow_nan=False).encode()
        require(len(encoded) <= 65536)
        with target.open("xb") as stream:
            stream.write(encoded)
        print(json.dumps({"status": "RequestVerified" if args.operation == "validate" else "NumericalResultBound",
                          "requestId": request.requestId, "experimentalValidation": False}))
        return 0
    except (Diagnostic, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "ReviewRequired", "reasonCode": error.code if isinstance(error, Diagnostic) else "GITHUB_CFD_WORKFLOW_INPUT_INVALID"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
