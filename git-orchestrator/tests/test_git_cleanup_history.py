import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_cleanup_history.sh"


class GitCleanupHistoryTests(unittest.TestCase):
    def run_cmd(self, cmd, cwd: Path, env=None, check: bool = True) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        merged_env["UV_CACHE_DIR"] = str(cwd / ".uv-cache")
        if env:
            merged_env.update(env)
        return subprocess.run(
            cmd,
            cwd=cwd,
            env=merged_env,
            check=check,
            capture_output=True,
            text=True,
        )

    def init_remote_repo(self, root: Path) -> tuple[Path, Path, Path]:
        remote = root / "remote.git"
        seed = root / "seed"
        work = root / "work"

        self.run_cmd(["git", "init", "--bare", str(remote)], cwd=root)
        seed.mkdir()
        self.run_cmd(["git", "init"], cwd=seed)
        self.run_cmd(["git", "config", "user.email", "test@example.com"], cwd=seed)
        self.run_cmd(["git", "config", "user.name", "tester"], cwd=seed)
        (seed / "README.md").write_text("main\n")
        (seed / "config.yaml").write_text("secret: one\n")
        (seed / ".gemini").mkdir()
        (seed / ".gemini" / ".env").write_text("GEMINI_SYSTEM_MD=one\n")
        self.run_cmd(["git", "add", "README.md", "config.yaml", ".gemini/.env"], cwd=seed)
        self.run_cmd(["git", "commit", "-m", "init"], cwd=seed)
        self.run_cmd(["git", "branch", "-M", "main"], cwd=seed)
        self.run_cmd(["git", "remote", "add", "origin", str(remote)], cwd=seed)
        self.run_cmd(["git", "push", "-u", "origin", "main"], cwd=seed)
        self.run_cmd(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)
        self.run_cmd(["git", "clone", str(remote), str(work)], cwd=root)
        self.run_cmd(["git", "config", "user.email", "test@example.com"], cwd=work)
        self.run_cmd(["git", "config", "user.name", "tester"], cwd=work)
        return remote, seed, work

    def test_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, work = self.init_remote_repo(Path(tmp))

            result = self.run_cmd(
                ["bash", str(SCRIPT), "--path", "config.yaml"],
                cwd=work,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("history rewrite confirmation required", result.stderr)

    def test_rewrites_history_restores_local_copies_and_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, _, work = self.init_remote_repo(root)

            result = self.run_cmd(
                [
                    "bash",
                    str(SCRIPT),
                    "--confirmed",
                    "--path",
                    "config.yaml",
                    "--path",
                    ".gemini/.env",
                ],
                cwd=work,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("history_cleanup=done", result.stdout)
            self.assertIn("upstream_status=restored", result.stdout)
            upstream = self.run_cmd(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=work,
            )
            self.assertEqual(upstream.stdout.strip(), "origin/main")
            history = self.run_cmd(
                ["git", "log", "--all", "--", "config.yaml", ".gemini/.env"],
                cwd=work,
            )
            self.assertEqual(history.stdout.strip(), "")
            tracked = self.run_cmd(
                ["git", "ls-files", "--", "config.yaml", ".gemini/.env"],
                cwd=work,
            )
            self.assertEqual(tracked.stdout.strip(), "")
            self.assertTrue((work / "config.yaml").exists())
            self.assertTrue((work / ".gemini" / ".env").exists())

            fresh = root / "fresh"
            self.run_cmd(["git", "clone", str(remote), str(fresh)], cwd=root)
            self.assertFalse((fresh / "config.yaml").exists())
            self.assertFalse((fresh / ".gemini" / ".env").exists())


if __name__ == "__main__":
    unittest.main()
