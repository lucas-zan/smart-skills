import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repo_policy.py"


def load_module():
    spec = importlib.util.spec_from_file_location("git_orchestrator_repo_policy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RepoPolicyTests(unittest.TestCase):
    def test_default_share_and_land_conflict_policy_is_safe(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            policy = module.load_policy(Path(tmp))

        share_and_land = policy["share_and_land"]
        self.assertFalse(share_and_land["auto_resolve_conflicts"])
        self.assertEqual(share_and_land["auto_resolve_conflicts_command"], "")
        self.assertEqual(share_and_land["allowed_conflict_paths"], [])
        self.assertEqual(share_and_land["blocked_conflict_paths"], [])
        self.assertEqual(share_and_land["max_conflict_resolution_attempts"], 3)

    def test_default_config_path_falls_back_to_skill_directory(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            config_path = repo_root / "git-orchestrator" / ".git-orchestrator.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "policy": {
                            "share_and_land": {
                                "allow_direct": False,
                            }
                        }
                    }
                )
            )

            policy = module.load_policy(repo_root)

        self.assertFalse(policy["share_and_land"]["allow_direct"])


if __name__ == "__main__":
    unittest.main()
