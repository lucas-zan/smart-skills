import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_commit_message.py"


class GenerateCommitMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmpdir.name)
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "tester")

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
            ["uv", "run", "python", str(SCRIPT), *args],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )

    def commit_file(self, relative_path: str, content: str, message: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.git("add", relative_path)
        self.git("commit", "-m", message)

    def test_default_mode_uses_staged_and_unstaged_changes(self) -> None:
        self.commit_file("src/a.txt", "one\n", "init a")
        self.commit_file("src/b.txt", "one\n", "init b")

        (self.repo / "src" / "a.txt").write_text("two\n")
        self.git("add", "src/a.txt")
        (self.repo / "src" / "b.txt").write_text("two\n")

        result = self.script("--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("src/a.txt", payload["body"])
        self.assertIn("src/b.txt", payload["body"])

    def test_staged_mode_excludes_unstaged_changes(self) -> None:
        self.commit_file("src/a.txt", "one\n", "init a")
        self.commit_file("src/b.txt", "one\n", "init b")

        (self.repo / "src" / "a.txt").write_text("two\n")
        self.git("add", "src/a.txt")
        (self.repo / "src" / "b.txt").write_text("two\n")

        result = self.script("--staged", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("src/a.txt", payload["body"])
        self.assertNotIn("src/b.txt", payload["body"])


if __name__ == "__main__":
    unittest.main()
