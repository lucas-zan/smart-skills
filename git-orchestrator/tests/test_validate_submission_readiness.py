import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_submission_readiness.py"


class ValidateSubmissionReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "tester")
        self.write("src/app.py", "print('base')\n")
        self.git("add", "src/app.py")
        self.git("commit", "-m", "init")
        self.write_config()

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

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, UV_CACHE_DIR=str(self.repo / ".uv-cache"))
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def write(self, relative_path: str, content: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def write_config(self, evidence_override: dict | None = None) -> None:
        evidence = {
            "enforce_before_commit": True,
            "pre_commit_checks_enabled": True,
            "require_requirements": True,
            "require_design": True,
            "require_tests": True,
            "require_test_docs": True,
            "require_todo": True,
        }
        if evidence_override:
            evidence.update(evidence_override)
        config = {
            "policy": {
                "evidence": evidence
            }
        }
        (self.repo / ".git-orchestrator.json").write_text(json.dumps(config, indent=2))

    def write_valid_delivery_docs(self, todo_body: str = "- [x] done\n") -> None:
        self.write("docs/requirements/feature.md", "# requirement\n")
        self.write("docs/design/feature.md", "# design\n")
        self.write("docs/tests/feature.md", "# test cases\n")
        self.write("docs/todo/feature.md", todo_body)
        self.write("tests/test_app.py", "def test_app():\n    assert True\n")
        self.write("src/app.py", "print('changed')\n")

    def test_fails_when_test_doc_and_todo_are_missing(self) -> None:
        self.write("docs/requirements/feature.md", "# requirement\n")
        self.write("docs/design/feature.md", "# design\n")
        self.write("tests/test_app.py", "def test_app():\n    assert True\n")
        self.write("src/app.py", "print('changed')\n")

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Submission readiness check failed", result.stderr)
        self.assertIn("test_docs", result.stderr)
        self.assertIn("todo", result.stderr)

    def test_fails_when_todo_has_unfinished_items(self) -> None:
        self.write_valid_delivery_docs(todo_body="- [x] done\n- [ ] pending\n")

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("todo_status", result.stderr)
        self.assertIn("unfinished TODO items", result.stderr)

    def test_passes_with_requirements_design_test_doc_test_code_and_completed_todo(self) -> None:
        self.write_valid_delivery_docs()

        result = self.run_script(
            "--requirement",
            "docs/requirements/feature.md",
            "--design",
            "docs/design/feature.md",
            "--test-doc",
            "docs/tests/feature.md",
            "--test",
            "tests/test_app.py",
            "--todo",
            "docs/todo/feature.md",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("todo_check_requirements=ok", result.stdout)
        self.assertIn("todo_check_design=ok", result.stdout)
        self.assertIn("todo_check_test_docs=ok", result.stdout)
        self.assertIn("todo_check_tests=ok", result.stdout)
        self.assertIn("todo_check_todo=ok", result.stdout)

    def test_skips_readiness_checks_when_pre_commit_checks_are_disabled(self) -> None:
        self.write_config({"pre_commit_checks_enabled": False})
        self.write("src/app.py", "print('changed')\n")

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("todo_check_requirements=skipped", result.stdout)
        self.assertIn("todo_check_design=skipped", result.stdout)
        self.assertIn("todo_check_test_docs=skipped", result.stdout)
        self.assertIn("todo_check_tests=skipped", result.stdout)
        self.assertIn("todo_check_todo=skipped", result.stdout)


if __name__ == "__main__":
    unittest.main()
