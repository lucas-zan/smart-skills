import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "resolve_workflow_inputs.py"


class ResolveWorkflowInputsTests(unittest.TestCase):
    def script(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_missing_config_reports_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.script(Path(tmp), "--workflow", "deploy.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workflow config file not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_required_input_reports_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".git-orchestrator.json"
            config_path.write_text(
                json.dumps(
                    {
                        "workflows": {
                            "deploy.yml": {
                                "required_inputs": ["environment"],
                                "default_inputs": {},
                            }
                        }
                    }
                )
            )

            result = self.script(root, "--workflow", "deploy.yml")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required workflow inputs: environment", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
