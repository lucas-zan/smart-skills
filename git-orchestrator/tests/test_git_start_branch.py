import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_start_branch.sh"


class GitStartBranchTests(unittest.TestCase):
    def test_defaults_to_current_branch_when_no_base_is_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            work = root / "work"

            self.run_cmd(["git", "init", "--bare", str(remote)], cwd=root)
            seed.mkdir()
            self.run_cmd(["git", "init"], cwd=seed)
            self.run_cmd(["git", "config", "user.email", "test@example.com"], cwd=seed)
            self.run_cmd(["git", "config", "user.name", "tester"], cwd=seed)

            (seed / "README.md").write_text("main\n")
            self.run_cmd(["git", "add", "README.md"], cwd=seed)
            self.run_cmd(["git", "commit", "-m", "init"], cwd=seed)
            self.run_cmd(["git", "branch", "-M", "main"], cwd=seed)
            self.run_cmd(["git", "remote", "add", "origin", str(remote)], cwd=seed)
            self.run_cmd(["git", "push", "-u", "origin", "main"], cwd=seed)

            self.run_cmd(["git", "switch", "-c", "dev"], cwd=seed)
            (seed / "dev.txt").write_text("dev\n")
            self.run_cmd(["git", "add", "dev.txt"], cwd=seed)
            self.run_cmd(["git", "commit", "-m", "dev"], cwd=seed)
            self.run_cmd(["git", "push", "-u", "origin", "dev"], cwd=seed)
            self.run_cmd(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)

            self.run_cmd(["git", "clone", str(remote), str(work)], cwd=root)
            self.run_cmd(["git", "switch", "dev"], cwd=work)

            result = self.run_cmd(
                ["bash", str(SCRIPT), "--slug", "demo"],
                cwd=work,
                env={"GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203"},
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("base_branch=dev", result.stdout)
            self.assertIn("feature_branch=agent/dev-20260415010203-demo", result.stdout)

    def test_defaults_to_remote_default_branch_when_base_not_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            work = root / "work"

            self.run_cmd(["git", "init", "--bare", str(remote)], cwd=root)
            seed.mkdir()
            self.run_cmd(["git", "init"], cwd=seed)
            self.run_cmd(["git", "config", "user.email", "test@example.com"], cwd=seed)
            self.run_cmd(["git", "config", "user.name", "tester"], cwd=seed)

            (seed / "README.md").write_text("main\n")
            self.run_cmd(["git", "add", "README.md"], cwd=seed)
            self.run_cmd(["git", "commit", "-m", "init"], cwd=seed)
            self.run_cmd(["git", "branch", "-M", "main"], cwd=seed)
            self.run_cmd(["git", "remote", "add", "origin", str(remote)], cwd=seed)
            self.run_cmd(["git", "push", "-u", "origin", "main"], cwd=seed)

            self.run_cmd(["git", "switch", "-c", "release"], cwd=seed)
            (seed / "release.txt").write_text("release\n")
            self.run_cmd(["git", "add", "release.txt"], cwd=seed)
            self.run_cmd(["git", "commit", "-m", "release"], cwd=seed)
            self.run_cmd(["git", "push", "-u", "origin", "release"], cwd=seed)
            self.run_cmd(["git", "symbolic-ref", "HEAD", "refs/heads/release"], cwd=remote)

            self.run_cmd(["git", "clone", str(remote), str(work)], cwd=root)

            result = self.run_cmd(
                ["bash", str(SCRIPT), "--slug", "demo"],
                cwd=work,
                env={"GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203"},
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("base_branch=release", result.stdout)
            self.assertIn("feature_branch=agent/release-20260415010203-demo", result.stdout)

    def run_cmd(self, cmd, cwd: Path, env=None, check: bool = True) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
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


if __name__ == "__main__":
    unittest.main()
