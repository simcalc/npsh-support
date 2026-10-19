"""Transport/contract fixtures only. These tests do not execute CFD or GitHub."""
from dataclasses import asdict, replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))
from github_cfd_job import (API, API_ROOT, Diagnostic, Jobs, LIMIT,
                            PROFILES, REPOSITORY, Request, WORKFLOW_PATH,
                            finite_json, main, read_archive, verified_report)
from github_cfd_workflow import pack, validate_environment

COMMIT_VALUE = "a" * 40  # Synthetic source binding, never a published CFD run.
REQUEST = Request("b" * 32, "transient-cavity-v1", COMMIT_VALUE)


def fake_report(request=REQUEST):
    return {"schemaVersion": "untirta.cfd-worker-manifest.v1", "caseProfile": request.caseProfile,
            **PROFILES[request.caseProfile], "status": "DevelopmentBenchmarkComplete",
            "actualCfdRun": True, "numericalSmokePassed": True, "sourceInputUnchanged": True,
            "referenceUnchanged": True, "engineeringValidated": False, "mainApplicationWrites": False}


def fake_run(**updates):
    return {"id": 12, "head_sha": COMMIT_VALUE, "display_title": REQUEST.title,
            "head_repository": {"full_name": REPOSITORY}, "path": WORKFLOW_PATH,
            "event": "workflow_dispatch", "run_attempt": 1,
            "status": "completed", "conclusion": "success", **updates}


def archive(value=None, filename="result.json"):
    target = BytesIO()
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr(filename, json.dumps(value if value is not None else pack(REQUEST, fake_report())))
    return target.getvalue()


class FakeTransport:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, headers, body=None, maximum=LIMIT):
        self.calls.append((method, url, headers, body))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        status, metadata, value = response
        return status, metadata, value if isinstance(value, bytes) else json.dumps(value).encode()


def fake_jobs(*responses):
    transport = FakeTransport(*responses)
    return Jobs(API("synthetic-test-token", transport), COMMIT_VALUE), transport


def fake_tag():
    return 200, {}, {"ref": "refs/tags/cfd-dev-" + COMMIT_VALUE, "object": {"type": "commit", "sha": COMMIT_VALUE}}


class GitHubCfdTests(unittest.TestCase):
    def assert_code(self, code, callback):
        with self.assertRaises(Diagnostic) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def test_prepare_is_input_only_and_does_not_contact_github(self):
        with TemporaryDirectory() as directory, patch("github_cfd_job.API") as api:
            path = Path(directory) / "request.json"
            with patch.object(sys, "argv", ["job", "prepare", "--request", str(path), "--profile", REQUEST.caseProfile, "--commit", COMMIT_VALUE]), patch("builtins.print"):
                self.assertEqual(main(), 0)
            self.assertEqual(set(json.loads(path.read_text())), set(asdict(REQUEST)))
            api.assert_not_called()

    def test_inputs_reject_shell_paths_unreviewed_commit_unknown_profile(self):
        for key, values in {"requestId": ["../abc", "$(whoami)", "B" * 32, 1],
                            "caseProfile": ["impeller-mrf-v1", "../outside", None, []],
                            "sourceCommit": ["main", "a" * 39, "a" * 40 + "\n", None]}.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(Diagnostic):
                    Request(**{**asdict(REQUEST), key: value})

    def test_source_mismatch_never_calls_api_including_status(self):
        jobs, transport = fake_jobs()
        wrong = replace(REQUEST, sourceCommit="c" * 40)
        for callback in (lambda: jobs.dispatch(wrong), lambda: jobs.status(wrong, 12), lambda: jobs.reconcile(wrong)):
            self.assert_code("GITHUB_CFD_BINDING_INVALID", callback)
        self.assertFalse(transport.calls)

    def test_dispatch_exact_commit_and_allowlisted_inputs(self):
        jobs, transport = fake_jobs(fake_tag(), (204, {}, b""))
        self.assertEqual(jobs.dispatch(REQUEST)["status"], "DispatchAccepted")
        self.assertEqual(len(transport.calls), 2)
        method, url, headers, body = transport.calls[1]
        self.assertEqual(method, "POST")
        self.assertEqual(json.loads(body), {"ref": "cfd-dev-" + COMMIT_VALUE, "inputs": {"request_id": REQUEST.requestId, "case_profile": REQUEST.caseProfile}})
        self.assertTrue(url.startswith(API_ROOT + "/actions/workflows/"))
        self.assertNotIn("synthetic-test-token", url + body.decode())

    def test_ambiguous_dispatch_preserves_attempt_receipt_and_never_retries(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(asdict(REQUEST)))
            jobs, transport = fake_jobs(fake_tag(), Diagnostic("GITHUB_CFD_TRANSPORT_UNCERTAIN", "Reconcile"))
            args = ["job", "dispatch", "--request", str(path)]
            with patch.object(sys, "argv", args), patch.dict("os.environ", {"GH_TOKEN": "test-only", "GITHUB_CFD_APPROVED_COMMIT": COMMIT_VALUE}), patch("github_cfd_job.API", return_value=jobs.api), patch("builtins.print"):
                self.assertEqual(main(), 2)
                self.assertEqual(main(), 2)
            self.assertEqual(len(transport.calls), 2)
            receipt = path.with_name("request.json.dispatch-attempt").read_text()
            self.assertEqual(json.loads(receipt), asdict(REQUEST))
            self.assertNotIn("token", receipt)

    def test_changed_or_annotated_tag_cannot_dispatch(self):
        for kind, digest in [("commit", "c" * 40), ("tag", COMMIT_VALUE)]:
            jobs, transport = fake_jobs((200, {}, {"ref": "refs/tags/cfd-dev-" + COMMIT_VALUE, "object": {"type": kind, "sha": digest}}))
            self.assert_code("GITHUB_CFD_REVIEWED_TAG_REQUIRED", lambda: jobs.dispatch(REQUEST))
            self.assertEqual(len(transport.calls), 1)

    def test_current_dispatch_api_returns_run_id(self):
        jobs, _ = fake_jobs(fake_tag(), (200, {}, {"workflow_run_id": 12, "run_url": API_ROOT + "/actions/runs/12"}))
        self.assertEqual(jobs.dispatch(REQUEST)["runId"], 12)

    def test_direct_run_receipt_avoids_bounded_history_search(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(asdict(REQUEST)))
            path.with_name("request.json.dispatch-result").write_text(json.dumps({"requestId": REQUEST.requestId, "runId": 12}))
            jobs, transport = fake_jobs((200, {}, fake_run()))
            with patch.object(sys, "argv", ["job", "status", "--request", str(path)]), patch.dict("os.environ", {"GH_TOKEN": "test-only", "GITHUB_CFD_APPROVED_COMMIT": COMMIT_VALUE}), patch("github_cfd_job.API", return_value=jobs.api), patch("builtins.print"):
                self.assertEqual(main(), 0)
            self.assertEqual(len(transport.calls), 1)
            self.assertTrue(transport.calls[0][1].endswith("/actions/runs/12"))

    def test_reconcile_matches_request_and_never_dispatches(self):
        unrelated = fake_run(display_title="different request")
        jobs, transport = fake_jobs((200, {}, {"workflow_runs": [unrelated, fake_run()]}))
        self.assertEqual(jobs.reconcile(REQUEST)["id"], 12)
        self.assertTrue(all(call[0] == "GET" for call in transport.calls))

    def test_invisible_request_is_not_retried(self):
        jobs, transport = fake_jobs((200, {}, {"workflow_runs": []}))
        self.assertIsNone(jobs.reconcile(REQUEST))
        self.assertEqual(len(transport.calls), 1)

    def test_duplicate_request_is_not_arbitrarily_selected(self):
        jobs, _ = fake_jobs((200, {}, {"workflow_runs": [fake_run(), fake_run(id=13)]}))
        self.assert_code("GITHUB_CFD_DUPLICATE_DISPATCH", lambda: jobs.reconcile(REQUEST))

    def test_run_substitution_or_rerun_cannot_publish_a_result(self):
        for updates in ({"head_sha": "c" * 40}, {"run_attempt": 2}, {"path": ".github/workflows/other.yml"},
                        {"event": "push"}, {"id": 13}, {"head_repository": {"full_name": "other/fork"}}):
            jobs, _ = fake_jobs((200, {}, fake_run(**updates)))
            self.assert_code("GITHUB_CFD_BINDING_INVALID", lambda: jobs.status(REQUEST, 12))

    def test_running_progress_exposes_only_reviewed_stage_name(self):
        for stage, expected in [("Run bounded native benchmark", "Run bounded native benchmark"), ("secret diagnostic text", None)]:
            jobs, _ = fake_jobs((200, {}, fake_run(status="in_progress", conclusion=None)),
                                (200, {}, {"jobs": [{"steps": [{"name": stage, "status": "in_progress"}]}]}))
            result = jobs.status(REQUEST, 12)
            self.assertEqual((result["status"], result["stage"], result["numericalResultVerified"]), ("Running", expected, False))

    def test_cancel_is_requested_until_github_confirms_terminal_state(self):
        jobs, transport = fake_jobs((200, {}, fake_run(status="queued", conclusion=None)), (200, {}, {"jobs": []}), (202, {}, b""))
        self.assertEqual(jobs.cancel(REQUEST, 12)["status"], "CancellationRequested")
        self.assertTrue(transport.calls[-1][1].endswith("/cancel"))
        jobs, transport = fake_jobs((200, {}, fake_run(conclusion="cancelled")))
        self.assertEqual(jobs.cancel(REQUEST, 12)["status"], "Cancelled")
        self.assertEqual(len(transport.calls), 1)

    def test_workflow_success_is_only_result_available(self):
        jobs, _ = fake_jobs((200, {}, fake_run()))
        self.assertEqual(jobs.status(REQUEST, 12), {"status": "ResultAvailable", "conclusion": "success", "runId": 12, "numericalResultVerified": False})

    def test_failed_workflow_cannot_download_or_publish_results(self):
        for conclusion in ["failure", "timed_out", "skipped", "action_required"]:
            jobs, transport = fake_jobs((200, {}, fake_run(conclusion=conclusion)))
            self.assert_code("GITHUB_CFD_RESULT_NOT_READY", lambda: jobs.result(REQUEST, 12))
            self.assertEqual(len(transport.calls), 1)

    def test_artifact_download_strips_authorization_and_verifies_binding(self):
        data = archive()
        metadata = {"id": 23, "name": "cfd-result-" + REQUEST.requestId, "expired": False,
                    "size_in_bytes": len(data), "digest": "sha256:" + sha256(data).hexdigest(),
                    "workflow_run": {"id": 12, "head_sha": COMMIT_VALUE}}
        jobs, transport = fake_jobs((200, {}, fake_run()), (200, {}, {"artifacts": [metadata]}),
                                    (302, {"location": "https://example.blob.core.windows.net/result.zip?sig=test-only"}, b""),
                                    (200, {}, data))
        result = jobs.result(REQUEST, 12)
        self.assertEqual(result["requestId"], REQUEST.requestId)
        self.assertEqual(set(transport.calls[-1][2]), {"Accept-Encoding"})
        self.assertNotIn("sig=", json.dumps(result))

    def test_expired_mismatched_or_duplicate_artifact_is_rejected_before_download(self):
        good = {"id": 23, "name": "cfd-result-" + REQUEST.requestId, "expired": False, "size_in_bytes": 500,
                "workflow_run": {"id": 12, "head_sha": COMMIT_VALUE}}
        cases = [[{**good, "expired": True}], [{**good, "size_in_bytes": LIMIT + 1}],
                 [{**good, "workflow_run": {"id": 13, "head_sha": COMMIT_VALUE}}], [good, good], []]
        for metadata in cases:
            jobs, transport = fake_jobs((200, {}, fake_run()), (200, {}, {"artifacts": metadata}))
            with self.assertRaises(Diagnostic):
                jobs.result(REQUEST, 12)
            self.assertEqual(len(transport.calls), 2)

    def test_storage_redirect_cannot_leak_token_or_reach_arbitrary_host(self):
        for location in ["http://example.blob.core.windows.net/x", "https://evil.invalid/x", "https://example.blob.core.windows.net.evil.invalid/x",
                         "https://user@example.blob.core.windows.net/x", "https://example.blob.core.windows.net:444/x", "https://example.blob.core.windows.net:bad/x"]:
            transport = FakeTransport((302, {"location": location}, b""))
            self.assert_code("GITHUB_CFD_DOWNLOAD_ORIGIN_REJECTED", lambda: API("synthetic-token", transport).call("GET", "/actions/artifacts/23/zip", raw=True))
            self.assertEqual(len(transport.calls), 1)

    def test_rate_limit_does_not_retry(self):
        for code, headers in [(429, {}), (403, {"x-ratelimit-remaining": "0"})]:
            transport = FakeTransport((code, headers, {}))
            self.assert_code("GITHUB_CFD_RATE_LIMIT", lambda: API("test-only", transport).call("GET", "/actions/runs/12"))
            self.assertEqual(len(transport.calls), 1)

    def test_nonfinite_duplicate_oversize_and_deep_json_are_rejected(self):
        for raw in [b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}', b"x" * (LIMIT + 1), b"[" * 2000 + b"0" + b"]" * 2000]:
            with self.assertRaises(Diagnostic):
                finite_json(raw)

    def test_archive_does_not_extract_traversal_zipbomb_links_or_extra_files(self):
        for filename in ["../result.json", "/result.json", "other.json"]:
            self.assert_code("GITHUB_CFD_ARTIFACT_INVALID", lambda: read_archive(REQUEST, archive(filename=filename)))
        for kind in ["link", "directory", "many", "bomb"]:
            target = BytesIO()
            with ZipFile(target, "w", compression=ZIP_DEFLATED) as zipped:
                if kind in {"link", "directory"}:
                    entry = ZipInfo("result.json")
                    entry.create_system, entry.external_attr = 3, (0o120777 if kind == "link" else 0o040755) << 16
                    zipped.writestr(entry, "target")
                elif kind == "many":
                    zipped.writestr("result.json", "{}")
                    zipped.writestr("another.json", "{}")
                else:
                    zipped.writestr("result.json", " " * 1000000)
            self.assert_code("GITHUB_CFD_ARTIFACT_INVALID", lambda: read_archive(REQUEST, target.getvalue()))

    def test_numeric_flags_and_hashes_must_be_exact_not_truthy(self):
        for key in ["inputSha256", "referenceSha256", "caseProfile", "status", "schemaVersion"]:
            with self.assertRaises(Diagnostic):
                verified_report(REQUEST, {**fake_report(), key: "wrong"})
        for key in ["actualCfdRun", "numericalSmokePassed", "sourceInputUnchanged", "referenceUnchanged", "engineeringValidated", "mainApplicationWrites"]:
            for value in [None, 1, "true"]:
                with self.assertRaises(Diagnostic):
                    verified_report(REQUEST, {**fake_report(), key: value})

    def test_result_envelope_is_bound_to_request_and_both_source_commits(self):
        value = pack(REQUEST, fake_report())
        self.assertEqual(read_archive(REQUEST, archive(value)), value)
        for key in ["schemaVersion", "requestId", "caseProfile", "sourceCommit", "openfoamCommit"]:
            with self.assertRaises(Diagnostic):
                read_archive(REQUEST, archive({**value, key: "wrong"}))

    def test_profile_metadata_matches_pinned_python_authority(self):
        sys.path.insert(0, str(ROOT / "modules/OpenFoam/services/cfd_worker/src"))
        from untirta_cfd_worker.contracts import digest
        from untirta_cfd_worker.profiles import benchmark_reference
        for profile, expected in PROFILES.items():
            reference = benchmark_reference(profile)
            source = {"schemaVersion": "untirta.cfd-worker-job.v1", "studyId": profile,
                      "inputRevision": "fixture-v3" if profile == "cavitation-bullet-v1" else "fixture-v1",
                      "adapter": "openfoam", "caseProfile": profile, "referenceSha256": digest(reference),
                      "limits": {"memoryBytes": 2147483648, "timeoutSeconds": 1200, "diskBytes": 268435456, "logBytes": 2097152, "threads": 1}, "parameters": {}}
            self.assertEqual(expected, {"inputSha256": digest(source), "referenceSha256": digest(reference)})

    def test_workflow_scope_rejects_non_actions_without_subprocess(self):
        with patch.dict("os.environ", {}, clear=True), patch("github_cfd_workflow.subprocess.check_output") as run:
            self.assert_code("GITHUB_CFD_DEVELOPMENT_SCOPE_REQUIRED", validate_environment)
            run.assert_not_called()

    def test_workflow_and_devcontainer_keep_execution_boundary(self):
        workflow = (ROOT / ".github/workflows/cfd-development-job.yml").read_text()
        self.assertIn("vars.CFD_DEVELOPMENT_JOBS_ENABLED == 'true'", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("inputs.", (ROOT / "tools/run_github_benchmark.sh").read_text())
        config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(config["forwardPorts"], [])
        self.assertNotIn("privileged", config)
        self.assertNotIn("runArgs", config)


if __name__ == "__main__":
    unittest.main()
