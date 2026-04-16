import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose_auth.py"


class DiagnoseAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills_env = ROOT.parent / ".env"
        self.skills_env_backup = self.skills_env.read_text() if self.skills_env.exists() else None

    def tearDown(self) -> None:
        if self.skills_env_backup is None:
            self.skills_env.unlink(missing_ok=True)
        else:
            self.skills_env.write_text(self.skills_env_backup)

    def run_script(self, *args: str, env=None, check: bool = True) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env is not None:
            merged_env.update(env)
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=ROOT,
            env=merged_env,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_github_https_with_token_is_ready(self) -> None:
        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": "demo-token"},
        )

        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["remote_kind"], "github_https")
        self.assertEqual(payload["github_owner"], "example")
        self.assertEqual(payload["github_repo"], "repo")

    def test_github_https_without_token_reports_advice(self) -> None:
        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": ""},
        )

        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready"])
        self.assertIn("Export CLAW_GITHUB_TOKEN", "\n".join(payload["advice"]))

    def test_github_https_uses_skills_dotenv_token_when_shell_env_is_empty(self) -> None:
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": ""},
        )

        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["checks"]["claw_github_token_present"])

    def test_github_ssh_reports_https_requirement(self) -> None:
        result = self.run_script(
            "--remote-url",
            "git@github.com:example/repo.git",
        )

        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["remote_kind"], "github_ssh")
        self.assertIn("Change origin to HTTPS", "\n".join(payload["advice"]))

    def test_can_inspect_repo_remote_when_remote_url_not_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/example/repo.git"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )

            result = subprocess.run(
                ["uv", "run", "python", str(SCRIPT)],
                cwd=repo,
                env={**os.environ, "CLAW_GITHUB_TOKEN": "demo-token"},
                check=True,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready"])

    def test_require_ready_fails_with_stderr_advice(self) -> None:
        result = self.run_script(
            "--remote-url",
            "git@github.com:example/repo.git",
            "--require-ready",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Change origin to HTTPS", result.stderr)
