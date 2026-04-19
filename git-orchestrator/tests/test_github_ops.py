import importlib.util
import io
import json
import tarfile
import tempfile
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
        self.uploaded_assets = []

    def repo_path(self) -> str:
        return "/repos/example/repo"

    def request(self, method, path, body=None, query=None):
        self.calls.append((method, path, body, query))
        if method == "PUT" and path.endswith("/pulls/9/merge"):
            return {
                "merged": True,
                "sha": "abc123",
                "message": "Pull Request successfully merged",
            }
        if method == "POST" and path.endswith("/dispatches"):
            return {}
        if method == "GET" and path.endswith("/actions/workflows/release.yml/runs"):
            return {
                "workflow_runs": [
                    {
                        "id": 91,
                        "status": "queued",
                        "conclusion": None,
                        "html_url": "https://example.test/runs/91",
                        "head_branch": "main",
                        "created_at": "2026-04-14T10:00:05Z",
                        "event": "workflow_dispatch",
                        "name": "release",
                    }
                ]
            }
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

    def workflow_dispatch_status(self, workflow):
        self.calls.append(("WORKFLOW_STATUS", workflow, None, None))
        return {
            "available": True,
            "default_branch": "main",
        }

    def resolve_commit_sha(self, ref):
        self.calls.append(("RESOLVE_SHA", ref, None, None))
        return "fc59364abcdef"

    def create_github_release(self, ref, tag_name=None):
        self.calls.append(("CREATE_RELEASE", ref, tag_name, None))
        resolved_tag = tag_name or "v2026.04.16-fc59364"
        return {
            "id": 201,
            "tag_name": resolved_tag,
            "html_url": f"https://example.test/releases/{resolved_tag}",
            "target_commitish": ref,
            "upload_url": "https://uploads.example.test/repos/example/repo/releases/201/assets{?name,label}",
            "assets": [],
        }

    def upload_release_asset(self, release, asset_path):
        self.uploaded_assets.append(asset_path)
        return {
            "name": asset_path.name,
            "size": asset_path.stat().st_size,
            "browser_download_url": f"https://example.test/assets/{asset_path.name}",
        }


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
        ), patch.object(module.GitHubClient, "_resolve_token", return_value="claw-token"):
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
        ), patch.object(module.GitHubClient, "_resolve_token", return_value="dotenv-token"):
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
        ), patch.object(module.GitHubClient, "_resolve_token", return_value="dotenv-token"):
            client = module.GitHubClient(owner=None, repo=None)

        self.assertEqual(client.token, "dotenv-token")

    def test_client_rejects_missing_github_api_token(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
            },
            clear=True,
        ), patch.object(module, "candidate_github_tokens", return_value=[]):
            with self.assertRaises(SystemExit) as ctx:
                module.GitHubClient(owner=None, repo=None)

        self.assertIn("Missing GitHub API token", str(ctx.exception))

    def test_client_uses_git_credential_token_when_claw_token_cannot_access_repo(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(
            module.os.environ,
            {
                "GITHUB_OWNER": "example",
                "GITHUB_REPO": "repo",
                "CLAW_GITHUB_TOKEN": "bad-token",
            },
            clear=True,
        ), patch.object(module, "candidate_github_tokens", return_value=["bad-token", "git-credential-token"]), patch.object(
            module.GitHubClient,
            "_token_has_repo_access",
            side_effect=[False, True],
        ):
            client = module.GitHubClient(owner=None, repo=None)

        self.assertEqual(client.token, "git-credential-token")

    def test_flow_auth_guard_stops_when_remote_is_not_ready(self) -> None:
        module = load_module()

        fake_diagnose = types.SimpleNamespace(
            infer_remote_url=lambda remote: "git@github.com:example/repo.git",
            build_diagnosis=lambda remote_url: {
                "remote_url": remote_url,
                "remote_kind": "github_ssh",
                "checks": {
                    "git_transport_ready": True,
                    "claw_github_token_present": False,
                    "github_api_auth_ready": False,
                },
                "ready": True,
                "advice": ["Current remote uses SSH for git transport.", "Export CLAW_GITHUB_TOKEN or switch origin to HTTPS."],
            },
            emit_text=lambda diagnosis, stream: stream.write("Export CLAW_GITHUB_TOKEN or switch origin to HTTPS.\n"),
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

    def test_dispatch_release_uses_configured_workflow_and_platforms(self) -> None:
        module = load_module()
        client = FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".git-orchestrator.json"
            config.write_text(
                json.dumps(
                    {
                        "release": {
                            "after_merge": {
                                "enabled": True,
                                "workflow": "release.yml",
                                "platforms": ["macos", "linux"],
                                "platform_input": "platforms",
                                "inputs": {"publish": "true"},
                            }
                        },
                        "workflows": {
                            "release.yml": {
                                "default_ref": "main",
                                "required_inputs": ["platforms", "publish"],
                                "allowed_inputs": ["platforms", "publish"],
                            }
                        },
                    }
                )
            )

            args = types.SimpleNamespace(
                config=str(config),
                ref=None,
                wait=False,
                timeout=30,
                interval=1,
                input=[],
            )

            stdout = io.StringIO()
            with patch.object(module.time, "time", side_effect=[1000.0, 1000.1]), redirect_stdout(stdout):
                module.cmd_dispatch_release(client, args)

        payload = module.json.loads(stdout.getvalue())
        self.assertTrue(payload["enabled"])
        self.assertTrue(payload["dispatched"])
        self.assertEqual(payload["workflow"], "release.yml")
        dispatch_call = next(
            call for call in client.calls if call[0] == "POST" and call[1].endswith("/actions/workflows/release.yml/dispatches")
        )
        self.assertEqual(dispatch_call[2]["ref"], "main")
        self.assertEqual(dispatch_call[2]["inputs"]["platforms"], "macos,linux")
        self.assertEqual(dispatch_call[2]["inputs"]["publish"], "true")

    def test_dispatch_release_without_config_does_not_require_auth(self) -> None:
        module = load_module()
        stdout = io.StringIO()

        with patch.object(
            module,
            "resolve_release_dispatch",
            return_value={"enabled": False, "dispatched": False, "reason": "not_configured"},
        ), patch.object(
            module,
            "ensure_auth_ready_for_flow",
            side_effect=AssertionError("auth should not run"),
        ), patch.object(module.sys, "argv", ["github_ops.py", "dispatch-release"]), redirect_stdout(stdout):
            module.main()

        payload = module.json.loads(stdout.getvalue())
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["reason"], "not_configured")

    def test_build_local_release_archives_creates_macos_and_linux_packages(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "README.md").write_text("hello\n")
            (repo_root / "LICENSE").write_text("license\n")
            (repo_root / ".gocache").mkdir()
            (repo_root / ".gocache" / "huge-cache").write_text("ignored\n")
            (repo_root / "build").mkdir()
            (repo_root / "build" / "app-linux").write_text("linux-binary\n")
            (repo_root / "build" / "app-macos").write_text("macos-binary\n")

            archives = module.build_local_release_archives(
                repo_root=repo_root,
                version="v2026.04.16-fc59364",
                platforms=["macos", "linux"],
                package_settings={
                    "mode": "prebuilt",
                    "binary_name": "app",
                    "prebuilt_binaries": {
                        "linux": ["build/app-linux"],
                        "macos": ["build/app-macos"],
                    },
                    "include_globs": ["README*", "LICENSE*"],
                },
            )

            self.assertEqual(
                sorted(path.name for path in archives),
                sorted(
                    [
                        f"{repo_root.name}-v2026.04.16-fc59364-macos.tar.gz",
                        f"{repo_root.name}-v2026.04.16-fc59364-linux.tar.gz",
                    ]
                ),
            )
            for archive in archives:
                with tarfile.open(archive, "r:gz") as bundle:
                    names = bundle.getnames()
                self.assertIn("README.md", names)
                self.assertIn("LICENSE", names)
                self.assertIn("app", names)
                self.assertNotIn(".gocache/huge-cache", names)
                self.assertNotIn("build/app-linux", names)
                self.assertNotIn("build/app-macos", names)

    def test_build_local_release_archives_can_build_go_binaries(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "go.mod").write_text("module example.com/demo\n\ngo 1.24\n")
            (repo_root / "main.go").write_text(
                "package main\n\nimport \"fmt\"\n\nfunc main() { fmt.Println(\"hello\") }\n"
            )
            (repo_root / "README.md").write_text("hello\n")

            calls = []

            def fake_run(cmd, cwd=None, check=None, env=None, **kwargs):
                calls.append((cmd, cwd, env))
                output_path = Path(cmd[cmd.index("-o") + 1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(f"built for {env['GOOS']}\n")
                return types.SimpleNamespace(returncode=0)

            with patch.object(module.subprocess, "run", side_effect=fake_run):
                archives = module.build_local_release_archives(
                    repo_root=repo_root,
                    version="v2026.04.16-fc59364",
                    platforms=["macos", "linux"],
                    package_settings={
                        "mode": "go",
                        "binary_name": "demo",
                        "main_package": ".",
                        "include_globs": ["README*"],
                        "arch": "amd64",
                    },
                )

            self.assertEqual(len(calls), 2)
            gooses = sorted(call[2]["GOOS"] for call in calls)
            self.assertEqual(gooses, ["darwin", "linux"])
            for archive in archives:
                with tarfile.open(archive, "r:gz") as bundle:
                    names = bundle.getnames()
                self.assertIn("demo", names)
                self.assertIn("README.md", names)
                self.assertNotIn("main.go", names)

    def test_dispatch_release_falls_back_to_local_release_assets(self) -> None:
        module = load_module()
        client = FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "README.md").write_text("hello\n")
            (repo_root / "dist").mkdir()
            (repo_root / "dist" / "app-linux").write_text("linux-binary\n")
            (repo_root / "dist" / "app-macos").write_text("macos-binary\n")
            config = repo_root / ".git-orchestrator.json"
            config.write_text(
                json.dumps(
                    {
                        "release": {
                            "after_merge": {
                                "enabled": True,
                                "workflow": "release.yml",
                                "platforms": ["macos", "linux"],
                                "inputs": {
                                    "publish": "true",
                                    "version": "v2026.04.16-fc59364",
                                },
                                "package": {
                                    "mode": "prebuilt",
                                    "binary_name": "app",
                                    "prebuilt_binaries": {
                                        "linux": ["dist/app-linux"],
                                        "macos": ["dist/app-macos"],
                                    },
                                    "include_globs": ["README*"],
                                },
                            }
                        },
                        "workflows": {
                            "release.yml": {
                                "default_ref": "main",
                                "required_inputs": ["platforms", "publish"],
                                "allowed_inputs": ["platforms", "publish", "version"],
                            }
                        },
                    }
                )
            )
            args = types.SimpleNamespace(
                config=str(config),
                ref="3.55.0-autofix",
                wait=False,
                timeout=30,
                interval=1,
                input=[],
            )

            with patch.object(module, "find_repo_root", return_value=repo_root), patch.object(
                client,
                "workflow_dispatch_status",
                return_value={
                    "available": False,
                    "reason": "workflow_not_visible_on_default_branch",
                    "default_branch": "main",
                    "message": "Not Found",
                },
            ), patch.object(module.Path, "cwd", return_value=repo_root):
                summary = module.dispatch_release(client, args)

        self.assertEqual(summary["mode"], "github_release_fallback")
        self.assertEqual(summary["release"]["tag_name"], "v2026.04.16-fc59364")
        self.assertEqual(
            sorted(asset["name"] for asset in summary["assets"]),
            sorted(
                [
                    f"{repo_root.name}-v2026.04.16-fc59364-macos.tar.gz",
                    f"{repo_root.name}-v2026.04.16-fc59364-linux.tar.gz",
                ]
            ),
        )
        self.assertEqual(len(client.uploaded_assets), 2)
        for archive in client.uploaded_assets:
            with tarfile.open(archive, "r:gz") as bundle:
                names = bundle.getnames()
            self.assertIn("README.md", names)
            self.assertIn("app", names)
            self.assertNotIn("dist/app-linux", names)
            self.assertNotIn("dist/app-macos", names)

    def test_merge_pr_triggers_release_after_merge_when_enabled(self) -> None:
        module = load_module()
        client = FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".git-orchestrator.json"
            config.write_text(
                json.dumps(
                    {
                        "release": {
                            "after_merge": {
                                "enabled": True,
                                "workflow": "release.yml",
                                "platforms": ["macos", "linux"],
                            }
                        },
                        "workflows": {
                            "release.yml": {
                                "default_ref": "main",
                                "required_inputs": ["platforms"],
                                "allowed_inputs": ["platforms"],
                            }
                        },
                    }
                )
            )
            args = types.SimpleNamespace(
                number=9,
                method="squash",
                sha=None,
                title=None,
                message=None,
                config=str(config),
                release_ref=None,
                skip_release_after_merge=False,
                wait_release=False,
                release_timeout=30,
                release_interval=1,
                release_input=[],
            )

            stdout = io.StringIO()
            with patch.object(module.time, "time", side_effect=[1000.0, 1000.1]), redirect_stdout(stdout):
                module.cmd_merge_pr(client, args)

        payload = module.json.loads(stdout.getvalue())
        self.assertTrue(payload["merged"])
        self.assertIn("release", payload)
        self.assertTrue(payload["release"]["dispatched"])
        dispatch_call = next(
            call for call in client.calls if call[0] == "POST" and call[1].endswith("/actions/workflows/release.yml/dispatches")
        )
        self.assertEqual(dispatch_call[2]["inputs"]["platforms"], "macos,linux")

    def test_skill_directory_default_config_enables_release_after_merge(self) -> None:
        module = load_module()
        repo_config = ROOT / ".git-orchestrator.json"

        release = module.resolve_release_dispatch(
            config_path=str(repo_config),
            ref=None,
            extra_inputs={},
        )

        self.assertTrue(release["enabled"])
        self.assertEqual(release["workflow"], "release.yml")
        self.assertEqual(release["ref"], "main")
        self.assertEqual(release["inputs"]["platforms"], "macos,linux")
        self.assertEqual(release["inputs"]["publish"], "true")

    def test_default_config_path_falls_back_to_skill_directory(self) -> None:
        module = load_module()
        release = module.resolve_release_dispatch(
            config_path=module.DEFAULT_CONFIG_FILE,
            ref=None,
            extra_inputs={},
        )

        self.assertTrue(release["enabled"])
        self.assertEqual(release["workflow"], "release.yml")


if __name__ == "__main__":
    unittest.main()
