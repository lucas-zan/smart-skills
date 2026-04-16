import importlib.util
import io
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "github_ops.py"


def load_module():
    spec = importlib.util.spec_from_file_location("git_orchestrator_github_ops", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def repo_path(self) -> str:
        return "/repos/example/repo"

    def request(self, method, path, body=None, query=None):
        self.calls.append((method, path, body, query))
        if method == "POST" and path.endswith("/dispatches"):
            return {}
        if method == "GET" and path.endswith("/actions/workflows/deploy.yml/runs"):
            return {
                "workflow_runs": [
                    {
                        "id": 77,
                        "status": "queued",
                        "conclusion": None,
                        "html_url": "https://example.test/runs/77",
                        "head_branch": "main",
                        "created_at": "2026-04-14T10:00:05Z",
                        "event": "workflow_dispatch",
                        "name": "deploy",
                    }
                ]
            }
        if method == "GET" and path.endswith("/actions/runs/77"):
            return {
                "id": 77,
                "name": "deploy",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://example.test/runs/77",
            }
        raise AssertionError(f"unexpected request: {(method, path, body, query)}")


class GitHubOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills_env = ROOT.parent / ".env"
        self.skills_env_backup = self.skills_env.read_text() if self.skills_env.exists() else None

    def tearDown(self) -> None:
        if self.skills_env_backup is None:
            self.skills_env.unlink(missing_ok=True)
        else:
            self.skills_env.write_text(self.skills_env_backup)

    def test_client_accepts_claw_github_token_env(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
                "CLAW_GITHUB_TOKEN": "claw-token",
            },
            clear=True,
        ):
            client = module.GitHubClient(owner=None, repo=None)

        self.assertEqual(client.token, "claw-token")

    def test_client_accepts_claw_github_token_from_skills_dotenv(self) -> None:
        module = load_module()
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
                "CLAW_GITHUB_TOKEN": "",
            },
            clear=True,
        ):
            client = module.GitHubClient(owner=None, repo=None)

        self.assertEqual(client.token, "dotenv-token")

    def test_client_prefers_claw_github_token_from_skills_dotenv(self) -> None:
        module = load_module()
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
                "CLAW_GITHUB_TOKEN": "process-token",
            },
            clear=True,
        ):
            client = module.GitHubClient(owner=None, repo=None)

        self.assertEqual(client.token, "dotenv-token")

    def test_client_rejects_missing_claw_github_token(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
            },
            clear=True,
        ):
            with self.assertRaises(SystemExit) as ctx:
                module.GitHubClient(owner=None, repo=None)

        self.assertIn("Missing CLAW_GITHUB_TOKEN", str(ctx.exception))

    def test_flow_auth_guard_stops_when_remote_is_not_ready(self) -> None:
        module = load_module()

        fake_diagnose = types.SimpleNamespace(
            infer_remote_url=lambda remote: "git@github.com:example/repo.git",
            build_diagnosis=lambda remote_url: {
                "remote_url": remote_url,
                "remote_kind": "github_ssh",
                "checks": {
                    "uses_https_for_github": False,
                    "claw_github_token_present": False,
                },
                "ready": False,
                "advice": ["Change origin to HTTPS"],
            },
            emit_text=lambda diagnosis, stream: stream.write("Change origin to HTTPS\n"),
        )

        with patch.object(module, "load_diagnose_module", return_value=fake_diagnose):
            with self.assertRaises(SystemExit) as ctx:
                module.ensure_auth_ready_for_flow()

        self.assertEqual(ctx.exception.code, 1)

    def test_dispatch_workflow_can_discover_run(self) -> None:
        module = load_module()
        client = FakeClient()
        args = types.SimpleNamespace(
            workflow="deploy.yml",
            ref="main",
            input=[],
            input_file=None,
            wait=False,
            timeout=30,
            interval=1,
        )

        stdout = io.StringIO()
        with patch.object(module.time, "time", side_effect=[1000.0, 1000.1]), redirect_stdout(stdout):
            module.cmd_dispatch_workflow(client, args)

        payload = module.json.loads(stdout.getvalue())
        self.assertTrue(payload["dispatched"])
        self.assertEqual(payload["run"]["id"], 77)
        self.assertEqual(payload["run"]["status"], "queued")

    def test_dispatch_workflow_can_wait_for_discovered_run(self) -> None:
        module = load_module()
        client = FakeClient()
        args = types.SimpleNamespace(
            workflow="deploy.yml",
            ref="main",
            input=[],
            input_file=None,
            wait=True,
            timeout=30,
            interval=1,
        )

        stdout = io.StringIO()
        with patch.object(module.time, "time", side_effect=[1000.0, 1000.1, 1000.2]), \
                patch.object(module.time, "sleep"), \
                redirect_stdout(stdout):
            module.cmd_dispatch_workflow(client, args)

        payload = module.json.loads(stdout.getvalue())
        self.assertEqual(payload["run"]["id"], 77)
        self.assertEqual(payload["run"]["conclusion"], "success")


if __name__ == "__main__":
    unittest.main()
