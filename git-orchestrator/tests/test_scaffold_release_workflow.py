import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scaffold_release_workflow.py"


class ScaffoldReleaseWorkflowTests(unittest.TestCase):
    def run_script(self, cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_generates_release_workflow_from_repo_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            config = repo / "git-orchestrator" / ".git-orchestrator.json"
            config.parent.mkdir(parents=True)
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
                                "required_inputs": ["platforms"],
                                "allowed_inputs": ["platforms", "publish", "version"],
                                "default_inputs": {"publish": "true"},
                            }
                        },
                    }
                )
            )

            result = self.run_script(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            workflow = repo / ".github" / "workflows" / "release.yml"
            self.assertTrue(workflow.is_file())
            content = workflow.read_text()
            self.assertIn("workflow_dispatch:", content)
            self.assertIn("platforms:", content)
            self.assertIn("default: \"macos,linux\"", content)
            self.assertIn("runs-on: ${{ matrix.runner }}", content)
            self.assertIn("macos-latest", content)
            self.assertIn("ubuntu-latest", content)
            self.assertIn("gh release create", content)
            self.assertIn("created=.github/workflows/release.yml", result.stdout)

    def test_refuses_to_overwrite_existing_workflow_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".github" / "workflows").mkdir(parents=True)
            workflow = repo / ".github" / "workflows" / "release.yml"
            workflow.write_text("name: keep-me\n")
            config = repo / "git-orchestrator" / ".git-orchestrator.json"
            config.parent.mkdir(parents=True)
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
                                "required_inputs": ["platforms"],
                                "allowed_inputs": ["platforms", "publish", "version"],
                            }
                        },
                    }
                )
            )

            result = self.run_script(repo, check=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(workflow.read_text(), "name: keep-me\n")


if __name__ == "__main__":
    unittest.main()
