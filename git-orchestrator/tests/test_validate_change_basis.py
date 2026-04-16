import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_change_basis.py"


class ValidateChangeBasisTests(unittest.TestCase):
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
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )

    def write(self, relative_path: str, content: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def write_config(self) -> None:
        config = {
            "policy": {
                "defaults": {
                    "base_branch_strategy": "current-branch",
                    "feature_branch_prefix": "agent",
                    "share_branch_prefix": "share",
                },
                "evidence": {
                    "enforce_before_commit": True,
                    "require_requirements": True,
                    "require_design": True,
                    "require_tests": True,
                },
            }
        }
        (self.repo / ".git-orchestrator.json").write_text(json.dumps(config, indent=2))

    def test_fails_when_requirement_and_design_are_missing(self) -> None:
        self.write("src/app.py", "print('changed')\n")
        self.write("tests/test_app.py", "def test_app():\n    assert True\n")

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required change basis", result.stderr)
        self.assertIn("requirements", result.stderr)
        self.assertIn("design", result.stderr)

    def test_passes_with_requirement_design_and_test_evidence(self) -> None:
        self.write("docs/requirements/feature.md", "# requirement\n")
        self.write("docs/design/feature.md", "# design\n")
        self.write("tests/test_app.py", "def test_app():\n    assert True\n")
        self.write("src/app.py", "print('changed')\n")

        result = self.run_script(
            "--requirement",
            "docs/requirements/feature.md",
            "--design",
            "docs/design/feature.md",
            "--test",
            "tests/test_app.py",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("requirements=ok", result.stdout)
        self.assertIn("design=ok", result.stdout)
        self.assertIn("tests=ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
