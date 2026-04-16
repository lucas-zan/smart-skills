import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_release_assets.py"


class BootstrapReleaseAssetsTests(unittest.TestCase):
    def run_script(self, cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_creates_repo_root_release_assets_from_skill_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            result = self.run_script(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            config = repo / ".git-orchestrator.json"
            workflow = repo / ".github" / "workflows" / "release.yml"
            self.assertTrue(config.is_file())
            self.assertTrue(workflow.is_file())
            payload = json.loads(config.read_text())
            self.assertTrue(payload["release"]["after_merge"]["enabled"])
            self.assertEqual(payload["release"]["after_merge"]["workflow"], "release.yml")
            self.assertIn("gh release create", workflow.read_text())
            self.assertIn("config_created=1", result.stdout)
            self.assertIn("workflow_created=1", result.stdout)

    def test_preserves_existing_repo_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".github" / "workflows").mkdir(parents=True)
            (repo / ".git-orchestrator.json").write_text('{"release":{"after_merge":{"enabled":true,"workflow":"release.yml"}}}\n')
            (repo / ".github" / "workflows" / "release.yml").write_text("name: existing\n")

            result = self.run_script(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((repo / ".git-orchestrator.json").read_text(), '{"release":{"after_merge":{"enabled":true,"workflow":"release.yml"}}}\n')
            self.assertEqual((repo / ".github" / "workflows" / "release.yml").read_text(), "name: existing\n")
            self.assertIn("config_created=0", result.stdout)
            self.assertIn("workflow_created=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
