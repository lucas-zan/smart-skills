import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_env.py"


def load_module():
    spec = importlib.util.spec_from_file_location("git_orchestrator_skill_env", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SkillEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills_env = ROOT.parent / ".env"
        self.skills_env_backup = self.skills_env.read_text() if self.skills_env.exists() else None

    def tearDown(self) -> None:
        if self.skills_env_backup is None:
            self.skills_env.unlink(missing_ok=True)
        else:
            self.skills_env.write_text(self.skills_env_backup)

    def test_get_env_prefers_skills_dotenv_over_process_env(self) -> None:
        module = load_module()
        self.skills_env.write_text("CLAW_GITHUB_TOKEN=dotenv-token\n")

        with patch.dict(os.environ, {"CLAW_GITHUB_TOKEN": "process-token"}, clear=True):
            self.assertEqual(module.get_env("CLAW_GITHUB_TOKEN"), "dotenv-token")

    def test_get_env_uses_process_env_when_dotenv_missing(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(os.environ, {"CLAW_GITHUB_TOKEN": "process-token"}, clear=True):
            self.assertEqual(module.get_env("CLAW_GITHUB_TOKEN"), "process-token")

    def test_get_env_returns_none_when_missing_everywhere(self) -> None:
        module = load_module()
        self.skills_env.unlink(missing_ok=True)

        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(module.get_env("CLAW_GITHUB_TOKEN"))


if __name__ == "__main__":
    unittest.main()
