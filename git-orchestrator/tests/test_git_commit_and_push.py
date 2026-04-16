import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_commit_and_push.sh"


class GitCommitAndPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "tester")
        (self.repo / "a.txt").write_text("one\n")
        self.git("add", "a.txt")
        self.git("commit", "-m", "init")
        (self.repo / ".git-orchestrator.json").write_text(
            "{\n"
            '  "policy": {\n'
            '    "evidence": {\n'
            '      "enforce_before_commit": true,\n'
            '      "require_requirements": true,\n'
            '      "require_design": true,\n'
            '      "require_tests": true\n'
            "    }\n"
            "  }\n"
            "}\n"
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_no_add_all_requires_staged_changes(self) -> None:
        (self.repo / "a.txt").write_text("two\n")

        result = self.script("--subject", "test(repo): demo", "--no-add-all", "--no-push")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No staged changes to commit", result.stderr)

    def test_no_add_all_commits_previously_staged_changes(self) -> None:
        (self.repo / "docs" / "requirements").mkdir(parents=True)
        (self.repo / "docs" / "requirements" / "feature.md").write_text("# req\n")
        (self.repo / "docs" / "design").mkdir(parents=True)
        (self.repo / "docs" / "design" / "feature.md").write_text("# design\n")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_feature.py").write_text("def test_feature():\n    assert True\n")
        (self.repo / "a.txt").write_text("two\n")
        self.git("add", "a.txt")

        result = self.script(
            "--subject",
            "test(repo): demo",
            "--no-add-all",
            "--no-push",
            "--requirement",
            "docs/requirements/feature.md",
            "--design",
            "docs/design/feature.md",
            "--test",
            "tests/test_feature.py",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("log", "-1", "--pretty=%s"), "test(repo): demo")

    def test_commit_is_blocked_when_change_basis_is_missing(self) -> None:
        (self.repo / "a.txt").write_text("two\n")

        result = self.script("--subject", "test(repo): demo", "--no-push")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required change basis", result.stderr)

    def test_commit_passes_with_requirement_design_and_test_evidence(self) -> None:
        (self.repo / "docs" / "requirements").mkdir(parents=True)
        (self.repo / "docs" / "requirements" / "feature.md").write_text("# req\n")
        (self.repo / "docs" / "design").mkdir(parents=True)
        (self.repo / "docs" / "design" / "feature.md").write_text("# design\n")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_feature.py").write_text("def test_feature():\n    assert True\n")
        (self.repo / "a.txt").write_text("two\n")

        result = self.script(
            "--subject",
            "test(repo): demo",
            "--no-push",
            "--requirement",
            "docs/requirements/feature.md",
            "--design",
            "docs/design/feature.md",
            "--test",
            "tests/test_feature.py",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("log", "-1", "--pretty=%s"), "test(repo): demo")


if __name__ == "__main__":
    unittest.main()
