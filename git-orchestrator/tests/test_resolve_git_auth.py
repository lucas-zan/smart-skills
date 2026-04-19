import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "resolve_git_auth.py"


class ResolveGitAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills_env = ROOT.parent / ".env"
        self.skills_env_backup = self.skills_env.read_text() if self.skills_env.exists() else None

    def tearDown(self) -> None:
        if self.skills_env_backup is None:
            self.skills_env.unlink(missing_ok=True)
        else:
            self.skills_env.write_text(self.skills_env_backup)

    def run_script(self, *args: str, env=None, check: bool = True) -> subprocess.CompletedProcess[str]:
        merged_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "TMPDIR": os.environ.get("TMPDIR", ""),
        }
        if env is not None:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            env=merged_env,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_local_remote_returns_empty_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script("--remote-url", f"{tmp}/remote.git")

        payload = json.loads(result.stdout)
        self.assertEqual(payload["git_args"], [])

    def test_https_github_remote_requires_claw_token(self) -> None:
        self.skills_env.unlink(missing_ok=True)

        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": ""},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing CLAW_GITHUB_TOKEN", result.stderr)

    def test_https_github_remote_uses_claw_token(self) -> None:
        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": "demo-token"},
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["git_args"][0:2], ["-c", "credential.helper="])
        self.assertIn("http.https://github.com/.extraheader=Authorization: Basic ", payload["git_args"][3])

    def test_https_github_remote_uses_token_from_skills_dotenv(self) -> None:
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": ""},
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["git_args"][0:2], ["-c", "credential.helper="])
        self.assertIn("http.https://github.com/.extraheader=Authorization: Basic ", payload["git_args"][3])

    def test_https_github_remote_prefers_token_from_skills_dotenv(self) -> None:
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": "process-token"},
        )

        payload = json.loads(result.stdout)
        self.assertIn("eC1hY2Nlc3MtdG9rZW46ZG90ZW52LXRva2Vu", payload["git_args"][3])

    def test_ssh_github_remote_uses_ssh_without_extra_args(self) -> None:
        result = self.run_script(
            "--remote-url",
            "git@github.com:example/repo.git",
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["git_args"], [])

    def test_https_github_remote_error_suggests_ssh_fallback(self) -> None:
        self.skills_env.unlink(missing_ok=True)

        result = self.run_script(
            "--remote-url",
            "https://github.com/example/repo.git",
            env={"CLAW_GITHUB_TOKEN": ""},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("switch origin to SSH", result.stderr)
