"""Prepared server-side Actions transport. No browser token or engineering maths.

Only fixed repository development benchmarks are implemented. This module does
not enable a production service, accept student pump inputs, or retry dispatch.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4
import zlib
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "simcalc/npsh-support"
WORKFLOW = "cfd-development-job.yml"
WORKFLOW_PATH = ".github/workflows/" + WORKFLOW
OPENFOAM_COMMIT = "bd0fefb59b79589e4a3cc56fc5b04c24cbec024a"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY
PROFILES = json.loads((ROOT / "catalog/github-cfd-profiles.json").read_text())
LIMIT = 262144
REPORT_LIMIT = 65536
ID = re.compile(r"[0-9a-f]{32}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class Diagnostic(Exception):
    def __init__(self, code, action):
        super().__init__(code)
        self.code, self.action = code, action


def require(condition, code="GITHUB_CFD_BINDING_INVALID", action="Use the reviewed request, source commit and matching first workflow attempt."):
    if not condition:
        raise Diagnostic(code, action)


def finite_json(raw, maximum=LIMIT):
    require(isinstance(raw, bytes) and len(raw) <= maximum, "GITHUB_CFD_RESPONSE_SIZE", "Inspect the bounded response; no partial result is published.")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite")
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 32:
                raise ValueError("nesting")
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise Diagnostic("GITHUB_CFD_RESPONSE_INVALID", "Expected finite, unique-key JSON. No result was substituted.") from None


@dataclass(frozen=True)
class Request:
    requestId: str
    caseProfile: str
    sourceCommit: str

    def __post_init__(self):
        require(isinstance(self.requestId, str) and ID.fullmatch(self.requestId)
                and isinstance(self.sourceCommit, str) and COMMIT.fullmatch(self.sourceCommit)
                and isinstance(self.caseProfile, str) and self.caseProfile in PROFILES)

    @classmethod
    def create(cls, profile, commit):
        return cls(uuid4().hex, profile, commit)

    @property
    def title(self):
        return f"cfd-dev/{self.caseProfile}/{self.requestId}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    """No implicit retry/redirect. Exceptions never expose URL query or headers."""
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, url, headers, body=None, maximum=LIMIT):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            try:
                response = self.opener.open(req, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                # Redirect bodies are not needed and signed locations remain in memory.
                data = b"" if response.code == 302 else response.read(maximum + 1)
                require(len(data) <= maximum, "GITHUB_CFD_RESPONSE_SIZE", "The response exceeds the bounded job transport limit.")
                return response.code, {k.lower(): v for k, v in response.headers.items()}, data
        except (OSError, urllib.error.URLError):
            raise Diagnostic("GITHUB_CFD_TRANSPORT_UNCERTAIN" if method == "POST" else "GITHUB_CFD_TRANSPORT_UNAVAILABLE",
                             "Reconcile the same request before taking further action. Never automatically repeat a dispatch.") from None


class API:
    def __init__(self, token, transport=None):
        require(isinstance(token, str) and 0 < len(token) <= 1024 and all(33 <= ord(c) <= 126 for c in token),
                "GITHUB_CFD_SERVER_CREDENTIAL_REQUIRED", "Provide a repository-scoped Actions credential only to the trusted backend.")
        self._token, self.transport = token, transport or Transport()

    def call(self, method, path, payload=None, *, raw=False):
        allowed_path = path.startswith("/actions/") or (method == "GET" and re.fullmatch(r"/git/ref/tags/cfd-dev-[0-9a-f]{40}", path))
        require(method in {"GET", "POST"} and allowed_path and ".." not in path and "#" not in path)
        data = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        status, headers, content = self.transport.request(method, API_ROOT + path, {
            "Authorization": "Bearer " + self._token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "untirta-cfd-development-adapter",
            "Content-Type": "application/json", "Accept-Encoding": "identity"}, data)
        if status == 429 or (status == 403 and headers.get("x-ratelimit-remaining") == "0"):
            raise Diagnostic("GITHUB_CFD_RATE_LIMIT", "Pause polling until the GitHub rate limit resets; do not dispatch again.")
        if raw:
            require(status == 302, "GITHUB_CFD_ARTIFACT_UNAVAILABLE", "The artifact is unavailable or expired. Do not replace it with a previous result.")
            target = headers.get("location", "")
            try:
                parsed = urllib.parse.urlsplit(target)
                host, port = parsed.hostname or "", parsed.port
            except ValueError:
                raise Diagnostic("GITHUB_CFD_DOWNLOAD_ORIGIN_REJECTED", "Expected a valid GitHub HTTPS artifact redirect.") from None
            require(parsed.scheme == "https" and port in {None, 443} and not parsed.username and not parsed.password
                    and not parsed.fragment and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
                    "GITHUB_CFD_DOWNLOAD_ORIGIN_REJECTED", "Use GitHub's HTTPS artifact storage redirect only.")
            # The GitHub API credential is deliberately absent from the storage request.
            code, _, archive = self.transport.request("GET", target, {"Accept-Encoding": "identity"})
            require(code == 200, "GITHUB_CFD_ARTIFACT_UNAVAILABLE", "Download the matching unexpired artifact; do not use cached results.")
            return archive
        require(status in {200, 201, 202, 204}, "GITHUB_CFD_API_REJECTED", "Inspect repository Actions permission, reviewed commit and workflow availability. Dispatch is never retried automatically.")
        return finite_json(content) if content else None


def verified_report(request, report):
    require(isinstance(report, dict))
    expected = PROFILES[request.caseProfile]
    require(report.get("schemaVersion") == "untirta.cfd-worker-manifest.v1"
            and report.get("caseProfile") == request.caseProfile
            and all(report.get(k) == v for k, v in expected.items())
            and report.get("status") == "DevelopmentBenchmarkComplete"
            and all(report.get(k) is True for k in ("actualCfdRun", "numericalSmokePassed", "sourceInputUnchanged", "referenceUnchanged"))
            and report.get("engineeringValidated") is False and report.get("mainApplicationWrites") is False,
            "GITHUB_CFD_NUMERICAL_RESULT_UNVERIFIED", "Inspect this run's solver report and exact fixture binding. Workflow success alone is not numerical success.")
    return report


def read_archive(request, archive):
    require(isinstance(archive, bytes) and len(archive) <= LIMIT)
    try:
        with ZipFile(BytesIO(archive)) as zipped:
            entries = zipped.infolist()
            require(len(entries) == 1 and entries[0].filename == "result.json"
                    and 0 < entries[0].file_size <= REPORT_LIMIT and not entries[0].flag_bits & 1
                    and (entries[0].external_attr >> 16) & 0o170000 in {0, 0o100000}
                    and not entries[0].is_dir(),
                    "GITHUB_CFD_ARTIFACT_INVALID", "Expected one bounded regular result.json; no archive files are extracted.")
            with zipped.open(entries[0]) as stream:
                value = finite_json(stream.read(REPORT_LIMIT + 1), REPORT_LIMIT)
    except (BadZipFile, OSError, RuntimeError, NotImplementedError, zlib.error, EOFError):
        raise Diagnostic("GITHUB_CFD_ARTIFACT_INVALID", "Inspect the matching bounded result archive; no partial result was published.") from None
    require(isinstance(value, dict) and value.get("schemaVersion") == "untirta.github-cfd-result.v1"
            and all(value.get(k) == v for k, v in asdict(request).items())
            and value.get("openfoamCommit") == OPENFOAM_COMMIT)
    verified_report(request, value.get("report"))
    return value


class Jobs:
    """An external authenticated service must enforce per-student authorization.

    This prepared connector intentionally exposes no public HTTP endpoint and no
    production enable switch. GitHub concurrency is not a durable student queue.
    """
    def __init__(self, api, approved_commit):
        require(isinstance(approved_commit, str) and COMMIT.fullmatch(approved_commit))
        self.api, self.approved_commit = api, approved_commit

    def check(self, request):
        require(isinstance(request, Request) and request.sourceCommit == self.approved_commit)

    def dispatch(self, request):
        self.check(request)
        # Dispatch accepts branch/tag names, not an assumed raw commit ref.
        # Require the reviewed lightweight tag and verify its exact target.
        tag = "cfd-dev-" + request.sourceCommit
        reference = self.api.call("GET", "/git/ref/tags/" + tag)
        require(isinstance(reference, dict) and reference.get("ref") == "refs/tags/" + tag
                and isinstance(reference.get("object"), dict)
                and reference.get("object", {}).get("type") == "commit"
                and reference["object"].get("sha") == request.sourceCommit,
                "GITHUB_CFD_REVIEWED_TAG_REQUIRED", "Create the reviewed lightweight cfd-dev-<commit> tag at this exact commit. Do not dispatch a moving branch.")
        response = self.api.call("POST", f"/actions/workflows/{WORKFLOW}/dispatches", {
            "ref": tag, "inputs": {"request_id": request.requestId, "case_profile": request.caseProfile}})
        result = {"status": "DispatchAccepted", "requestId": request.requestId,
                  "action": "Poll for this exact request. Do not dispatch it again."}
        # Current API returns a run ID. Older deployments may return no body.
        if response is not None:
            require(isinstance(response, dict) and type(response.get("workflow_run_id")) is int and response["workflow_run_id"] > 0)
            result["runId"] = response["workflow_run_id"]
        return result

    def _run(self, request, run):
        self.check(request)
        require(isinstance(run, dict) and type(run.get("id")) is int and run["id"] > 0
                and run.get("head_sha") == request.sourceCommit and run.get("display_title") == request.title
                and run.get("path") == WORKFLOW_PATH and run.get("event") == "workflow_dispatch"
                and run.get("run_attempt") == 1
                and isinstance(run.get("head_repository"), dict)
                and run.get("head_repository", {}).get("full_name") == REPOSITORY)
        return run

    def reconcile(self, request):
        self.check(request)
        matches = []
        for page in range(1, 6):
            response = self.api.call("GET", f"/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=20&page={page}")
            require(isinstance(response, dict) and isinstance(response.get("workflow_runs"), list))
            runs = response["workflow_runs"]
            for run in runs:
                require(isinstance(run, dict))
                if run.get("display_title") == request.title:
                    matches.append(self._run(request, run))
            if len(runs) < 20:
                break
        require(len(matches) <= 1, "GITHUB_CFD_DUPLICATE_DISPATCH", "Multiple runs match the request. An administrator must inspect them; no result is selected automatically.")
        return matches[0] if matches else None

    def status(self, request, run_id):
        self.check(request)
        require(type(run_id) is int and run_id > 0)
        run = self._run(request, self.api.call("GET", f"/actions/runs/{run_id}"))
        require(run["id"] == run_id)
        state = run.get("status")
        if state == "completed":
            conclusion = run.get("conclusion")
            require(conclusion in {"success", "failure", "cancelled", "timed_out", "action_required", "skipped", "stale", "neutral", "startup_failure"})
            return {"status": "ResultAvailable" if conclusion == "success" else "Cancelled" if conclusion == "cancelled" else "Stopped",
                    "conclusion": conclusion, "runId": run_id, "numericalResultVerified": False}
        require(state in {"queued", "in_progress", "waiting", "pending", "requested"})
        response = self.api.call("GET", f"/actions/runs/{run_id}/jobs?per_page=100")
        require(isinstance(response, dict))
        jobs = response.get("jobs", [])
        require(isinstance(jobs, list) and len(jobs) <= 1 and all(isinstance(job, dict) and isinstance(job.get("steps", []), list)
                and all(isinstance(step, dict) for step in job.get("steps", [])) for job in jobs))
        active = next((step.get("name") for job in jobs for step in job.get("steps", []) if step.get("status") == "in_progress"), None)
        # Only known workflow stage labels are projected, never arbitrary log text.
        stage = active if active in {"Validate request and source", "Install pinned OpenFOAM", "Run bounded native benchmark", "Bind numerical result"} else None
        return {"status": "Running" if state == "in_progress" else "Queued", "runId": run_id,
                "stage": stage, "numericalResultVerified": False}

    def cancel(self, request, run_id):
        status = self.status(request, run_id)
        if status["status"] not in {"Stopped", "Cancelled", "ResultAvailable"}:
            self.api.call("POST", f"/actions/runs/{run_id}/cancel")
            return {"status": "CancellationRequested", "runId": run_id}
        return status

    def result(self, request, run_id):
        require(self.status(request, run_id)["status"] == "ResultAvailable", "GITHUB_CFD_RESULT_NOT_READY", "Wait for the exact run to finish; previous results are never used.")
        response = self.api.call("GET", f"/actions/runs/{run_id}/artifacts?per_page=100")
        require(isinstance(response, dict) and isinstance(response.get("artifacts"), list)
                and all(isinstance(a, dict) for a in response["artifacts"]))
        matches = [a for a in response.get("artifacts", []) if a.get("name") == "cfd-result-" + request.requestId]
        require(len(matches) == 1, "GITHUB_CFD_ARTIFACT_UNAVAILABLE", "Expected exactly one matching result artifact; check retention and upload status.")
        artifact = matches[0]
        require(artifact.get("expired") is False and type(artifact.get("id")) is int and artifact["id"] > 0
                and type(artifact.get("size_in_bytes")) is int and 0 < artifact["size_in_bytes"] <= LIMIT
                and isinstance(artifact.get("workflow_run"), dict)
                and artifact.get("workflow_run", {}).get("id") == run_id
                and artifact.get("workflow_run", {}).get("head_sha") == request.sourceCommit)
        archive = self.api.call("GET", f"/actions/artifacts/{artifact['id']}/zip", raw=True)
        digest = artifact.get("digest")
        if digest is not None:
            require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                    and digest == "sha256:" + sha256(archive).hexdigest())
        return read_archive(request, archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "dispatch", "status", "cancel", "result"))
    parser.add_argument("--request", type=Path, required=True, help="Input-only job binding; never a credential file")
    parser.add_argument("--profile", choices=tuple(PROFILES))
    parser.add_argument("--commit", help="Reviewed exact support repository commit")
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            request = Request.create(args.profile, args.commit)
            args.request.parent.mkdir(parents=True, exist_ok=True)
            with args.request.open("x", encoding="utf-8") as output:
                json.dump(asdict(request), output, indent=2)
            result = {"status": "Prepared", **asdict(request), "dispatched": False}
        else:
            require(args.request.stat().st_size <= 4096)
            value = finite_json(args.request.read_bytes(), 4096)
            require(isinstance(value, dict) and set(value) == {"requestId", "caseProfile", "sourceCommit"})
            request = Request(**value)
            jobs = Jobs(API(os.environ.get("GH_TOKEN", "")), os.environ.get("GITHUB_CFD_APPROVED_COMMIT", ""))
            if args.operation == "dispatch":
                jobs.check(request)
                try:
                    with args.request.with_name(args.request.name + ".dispatch-attempt").open("x", encoding="utf-8") as receipt:
                        json.dump(asdict(request), receipt)
                except FileExistsError:
                    raise Diagnostic("GITHUB_CFD_DISPATCH_ALREADY_ATTEMPTED", "Reconcile this request with status. Keep the receipt after a timeout; do not dispatch again.") from None
                result = jobs.dispatch(request)
                # A separate exclusive receipt preserves the current API's run
                # ID without altering the input-only request or retry marker.
                with args.request.with_name(args.request.name + ".dispatch-result").open("x", encoding="utf-8") as receipt:
                    json.dump(result, receipt)
            else:
                receipt_path = args.request.with_name(args.request.name + ".dispatch-result")
                if receipt_path.exists():
                    require(receipt_path.stat().st_size <= 4096)
                    receipt = finite_json(receipt_path.read_bytes(), 4096)
                    require(isinstance(receipt, dict) and receipt.get("requestId") == request.requestId)
                    run_id = receipt.get("runId")
                else:
                    run_id = None
                if run_id is None:
                    run = jobs.reconcile(request)
                    run_id = run["id"] if run else None
                result = {"status": "AwaitingRunVisibility", "action": "Keep the request ID. Do not dispatch again."} if run_id is None else getattr(jobs, args.operation)(request, run_id)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (Diagnostic, OSError, TypeError, ValueError) as error:
        result = {"status": "ReviewRequired", "reasonCode": error.code if isinstance(error, Diagnostic) else "GITHUB_CFD_REQUEST_FILE_INVALID",
                  "action": error.action if isinstance(error, Diagnostic) else "Inspect the bounded request file and exact reviewed commit; credentials must stay outside this file."}
        print(json.dumps(result, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
