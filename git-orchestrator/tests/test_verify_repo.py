import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_repo.sh"


class VerifyRepoTests(unittest.TestCase):
    def test_verify_cmd_override_runs_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "marker.txt"
            env = os.environ.copy()
            env["VERIFY_CMD"] = f"printf ok > {marker}"

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=tmp,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(marker.read_text(), "ok")

    def test_verify_without_detectable_command_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=tmp,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Could not determine a verification command automatically", result.stderr)


if __name__ == "__main__":
    unittest.main()
