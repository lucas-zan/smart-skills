import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_share_and_land.sh"


class GitShareAndLandTests(unittest.TestCase):
    def write_policy(self, repo: Path, policy: dict) -> None:
        (repo / ".git-orchestrator.json").write_text(json.dumps({"policy": policy}, indent=2))

    def write_config(self, repo: Path, payload: dict) -> None:
        (repo / ".git-orchestrator.json").write_text(json.dumps(payload, indent=2))

    def test_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.init_repo(Path(tmp))
            (repo / "README.md").write_text("changed\n")

            result = self.run_script(
                repo,
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share demo",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--confirmed is required", result.stderr)

    def test_pushes_feature_branch_and_merges_back_latest_remote_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            teammate = root / "teammate"

            self.init_remote(remote, seed)
            self.clone(remote, worker)
            self.clone(remote, teammate)

            self.git(teammate, "config", "user.email", "test@example.com")
            self.git(teammate, "config", "user.name", "tester")
            (teammate / "upstream.txt").write_text("from teammate\n")
            self.git(teammate, "add", "upstream.txt")
            self.git(teammate, "commit", "-m", "feat(repo): teammate change")
            self.git(teammate, "push", "origin", "main")

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.write_policy(
                worker,
                {
                    "share_and_land": {"allow_direct": True},
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "local.txt").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("feature_branch=share/main-20260415010203-demo", result.stdout)
            self.assertIn("merge=done", result.stdout)

            remote_heads = self.run_cmd(["git", "ls-remote", "--heads", str(remote)], cwd=root)
            self.assertIn("refs/heads/share/main-20260415010203-demo", remote_heads.stdout)

            landed = root / "landed"
            self.clone(remote, landed)
            self.assertEqual((landed / "local.txt").read_text(), "from worker\n")
            self.assertEqual((landed / "upstream.txt").read_text(), "from teammate\n")

        self.assertEqual(result.returncode, 0)

    def test_verify_failure_keeps_feature_branch_without_merging_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.write_policy(
                worker,
                {
                    "share_and_land": {"allow_direct": True},
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "local.txt").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "false",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verification=failed", result.stdout)
            self.assertIn("merge=not_attempted", result.stdout)

            remote_heads = self.run_cmd(["git", "ls-remote", "--heads", str(remote)], cwd=root)
            self.assertIn("refs/heads/share/main-20260415010203-demo", remote_heads.stdout)

            landed = root / "landed"
            self.clone(remote, landed)
            self.assertFalse((landed / "local.txt").exists())

    def test_without_policy_uses_current_branch_default_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            (worker / "go.mod").write_text("module example.com/demo\n\ngo 1.24\n")
            (worker / "docs" / "requirements").mkdir(parents=True)
            (worker / "docs" / "design").mkdir(parents=True)
            (worker / "docs" / "tests").mkdir(parents=True)
            (worker / "docs" / "todo").mkdir(parents=True)
            (worker / "tests").mkdir()
            (worker / "docs" / "requirements" / "demo.md").write_text("requirement\n")
            (worker / "docs" / "design" / "demo.md").write_text("design\n")
            (worker / "docs" / "tests" / "demo.md").write_text("test cases\n")
            (worker / "docs" / "todo" / "demo.md").write_text("- [x] done\n")
            (worker / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n")
            (worker / "local.txt").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                "--requirement",
                "docs/requirements/demo.md",
                "--design",
                "docs/design/demo.md",
                "--test-doc",
                "docs/tests/demo.md",
                "--test",
                "tests/test_demo.py",
                "--todo",
                "docs/todo/demo.md",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("base_branch=main", result.stdout)
            self.assertIn("feature_branch=share/main-20260415010203-demo", result.stdout)
            self.assertIn("merge=done", result.stdout)

    def test_base_branch_change_after_share_forces_reverify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            teammate = root / "teammate"

            self.init_remote(remote, seed)
            self.clone(remote, worker)
            self.clone(remote, teammate)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.write_policy(
                worker,
                {
                    "share_and_land": {"allow_direct": True, "reverify_on_base_change": True},
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "local.txt").write_text("from worker\n")

            hook = (
                f"git -C {teammate} config user.email test@example.com && "
                f"git -C {teammate} config user.name tester && "
                f"printf 'from teammate\\n' > {teammate / 'after-share.txt'} && "
                f"git -C {teammate} add after-share.txt && "
                f"git -C {teammate} commit -m 'feat(repo): after share' >/dev/null && "
                f"git -C {teammate} push origin main >/dev/null"
            )
            verify = (
                "uv run python - <<'PY'\n"
                "from pathlib import Path\n"
                "p = Path('verify-count.txt')\n"
                "count = int(p.read_text()) + 1 if p.exists() else 1\n"
                "p.write_text(str(count))\n"
                "PY"
            )

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": verify,
                    "POST_SHARE_CMD": hook,
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((worker / "verify-count.txt").read_text(), "2")

    def test_auto_resolves_rebase_conflict_for_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            teammate = root / "teammate"

            self.init_remote(remote, seed)
            self.clone(remote, worker)
            self.clone(remote, teammate)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.git(teammate, "config", "user.email", "test@example.com")
            self.git(teammate, "config", "user.name", "tester")

            (teammate / "README.md").write_text("from teammate\n")
            self.git(teammate, "add", "README.md")
            self.git(teammate, "commit", "-m", "feat(repo): teammate update")
            self.git(teammate, "push", "origin", "main")

            self.write_policy(
                worker,
                {
                    "share_and_land": {
                        "allow_direct": True,
                        "auto_resolve_conflicts": True,
                        "auto_resolve_conflicts_command": "printf 'from teammate\\nfrom worker\\n' > README.md",
                        "allowed_conflict_paths": ["README.md"],
                    },
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "README.md").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("conflict_resolution=resolved", result.stdout)

            landed = root / "landed"
            self.clone(remote, landed)
            self.assertEqual((landed / "README.md").read_text(), "from teammate\nfrom worker\n")

    def test_blocked_conflict_paths_require_manual_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            teammate = root / "teammate"

            self.init_remote(remote, seed)
            self.clone(remote, worker)
            self.clone(remote, teammate)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.git(teammate, "config", "user.email", "test@example.com")
            self.git(teammate, "config", "user.name", "tester")

            (seed / "db").mkdir(exist_ok=True)
            (seed / "db" / "schema.sql").write_text("select 1;\n")
            self.git(seed, "add", "db/schema.sql")
            self.git(seed, "commit", "-m", "feat(repo): add schema")
            self.git(seed, "push", "origin", "main")
            self.git(worker, "pull", "--ff-only", "origin", "main")
            self.git(teammate, "pull", "--ff-only", "origin", "main")

            (teammate / "db" / "schema.sql").write_text("select 2;\n")
            self.git(teammate, "add", "db/schema.sql")
            self.git(teammate, "commit", "-m", "feat(repo): teammate schema change")
            self.git(teammate, "push", "origin", "main")

            self.write_policy(
                worker,
                {
                    "share_and_land": {
                        "allow_direct": True,
                        "auto_resolve_conflicts": True,
                        "auto_resolve_conflicts_command": "printf invoked > resolver.txt",
                        "blocked_conflict_paths": ["db/**"],
                    },
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "db" / "schema.sql").write_text("select 3;\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflict_resolution=blocked", result.stdout)
            self.assertIn("Auto-resolve is not allowed", result.stderr)
            self.assertFalse((worker / "resolver.txt").exists())

    def test_failed_auto_resolution_stops_for_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            teammate = root / "teammate"

            self.init_remote(remote, seed)
            self.clone(remote, worker)
            self.clone(remote, teammate)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.git(teammate, "config", "user.email", "test@example.com")
            self.git(teammate, "config", "user.name", "tester")

            (teammate / "README.md").write_text("from teammate\n")
            self.git(teammate, "add", "README.md")
            self.git(teammate, "commit", "-m", "feat(repo): teammate update")
            self.git(teammate, "push", "origin", "main")

            self.write_policy(
                worker,
                {
                    "share_and_land": {
                        "allow_direct": True,
                        "auto_resolve_conflicts": True,
                        "auto_resolve_conflicts_command": "true",
                        "allowed_conflict_paths": ["README.md"],
                    },
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "README.md").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflict_resolution=failed", result.stdout)
            self.assertIn("left merge markers", result.stderr)

    def test_protected_branch_policy_requires_pull_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.write_policy(
                worker,
                {
                    "share_and_land": {
                        "allow_direct": True,
                        "protected_branches": ["main"],
                        "protected_branch_mode": "require-pull-request",
                    },
                    "evidence": {"enforce_before_commit": False},
                },
            )
            (worker / "local.txt").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("merge=pull_request_required", result.stdout)

    def test_merge_success_triggers_release_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            self.write_config(
                worker,
                {
                    "policy": {
                        "share_and_land": {"allow_direct": True},
                        "evidence": {"enforce_before_commit": False},
                    },
                    "release": {
                        "after_merge": {
                            "enabled": True,
                            "workflow": "release.yml",
                            "platforms": ["macos", "linux"],
                        }
                    },
                    "workflows": {
                        "release.yml": {
                            "default_ref": "main",
                            "required_inputs": ["platforms"],
                            "allowed_inputs": ["platforms"],
                        }
                    },
                },
            )
            (worker / "local.txt").write_text("from worker\n")

            fakebin, record_path = self.make_uv_wrapper(root)
            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                    "PATH": f"{fakebin}{os.pathsep}{os.environ['PATH']}",
                    "GIT_ORCHESTRATOR_RELEASE_RECORD": str(record_path),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("merge=done", result.stdout)
            self.assertIn("release=triggered", result.stdout)
            record = record_path.read_text()
            self.assertIn("dispatch-release", record)
            self.assertIn("--ref", record)
            self.assertIn("main", record)

    def test_with_release_bootstraps_release_assets_before_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            (worker / "go.mod").write_text("module example.com/demo\n\ngo 1.24\n")
            (worker / "docs" / "requirements").mkdir(parents=True)
            (worker / "docs" / "design").mkdir(parents=True)
            (worker / "docs" / "tests").mkdir(parents=True)
            (worker / "docs" / "todo").mkdir(parents=True)
            (worker / "tests").mkdir()
            (worker / "docs" / "requirements" / "demo.md").write_text("requirement\n")
            (worker / "docs" / "design" / "demo.md").write_text("design\n")
            (worker / "docs" / "tests" / "demo.md").write_text("test cases\n")
            (worker / "docs" / "todo" / "demo.md").write_text("- [x] done\n")
            (worker / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n")

            fakebin, record_path = self.make_uv_wrapper(root)
            result = self.run_script(
                worker,
                "--confirmed",
                "--with-release",
                "--slug",
                "demo",
                "--subject",
                "build(release): bootstrap automation",
                "--requirement",
                "docs/requirements/demo.md",
                "--design",
                "docs/design/demo.md",
                "--test-doc",
                "docs/tests/demo.md",
                "--test",
                "tests/test_demo.py",
                "--todo",
                "docs/todo/demo.md",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                    "PATH": f"{fakebin}{os.pathsep}{os.environ['PATH']}",
                    "GIT_ORCHESTRATOR_RELEASE_RECORD": str(record_path),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("release=triggered", result.stdout)
            self.assertIn("release_bootstrap=created", result.stdout)

            landed = root / "landed"
            self.clone(remote, landed)
            self.assertTrue((landed / ".git-orchestrator.json").is_file())
            self.assertTrue((landed / ".github" / "workflows" / "release.yml").is_file())
            self.assertFalse((landed / "git-orchestrator").exists())
            self.assertIn("workflow_dispatch:", (landed / ".github" / "workflows" / "release.yml").read_text())

    def test_share_and_land_stops_when_todo_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"

            self.init_remote(remote, seed)
            self.clone(remote, worker)

            self.git(worker, "config", "user.email", "test@example.com")
            self.git(worker, "config", "user.name", "tester")
            (worker / "docs" / "requirements").mkdir(parents=True)
            (worker / "docs" / "design").mkdir(parents=True)
            (worker / "docs" / "tests").mkdir(parents=True)
            (worker / "docs" / "todo").mkdir(parents=True)
            (worker / "tests").mkdir()
            (worker / "docs" / "requirements" / "demo.md").write_text("requirement\n")
            (worker / "docs" / "design" / "demo.md").write_text("design\n")
            (worker / "docs" / "tests" / "demo.md").write_text("test cases\n")
            (worker / "docs" / "todo" / "demo.md").write_text("- [x] done\n- [ ] pending\n")
            (worker / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n")
            (worker / "local.txt").write_text("from worker\n")

            result = self.run_script(
                worker,
                "--confirmed",
                "--slug",
                "demo",
                "--subject",
                "feat(repo): share worker change",
                "--requirement",
                "docs/requirements/demo.md",
                "--design",
                "docs/design/demo.md",
                "--test-doc",
                "docs/tests/demo.md",
                "--test",
                "tests/test_demo.py",
                "--todo",
                "docs/todo/demo.md",
                env={
                    "VERIFY_CMD": "true",
                    "GIT_ORCHESTRATOR_BRANCH_DATE": "20260415010203",
                },
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Submission readiness check failed", result.stderr)
            self.assertIn("todo_status", result.stderr)

    def make_uv_wrapper(self, root: Path) -> tuple[Path, Path]:
        real_uv = shutil.which("uv")
        self.assertIsNotNone(real_uv)

        fakebin = root / "fakebin"
        fakebin.mkdir()
        record_path = root / "release-dispatch.log"
        wrapper = fakebin / "uv"
        wrapper.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"run\" ] && [ \"$2\" = \"python\" ] && "
            "printf '%s' \"$3\" | grep -q 'github_ops.py$' && [ \"$4\" = \"dispatch-release\" ]; then\n"
            "  printf '%s\\n' \"$@\" > \"$GIT_ORCHESTRATOR_RELEASE_RECORD\"\n"
            "  printf '{\"enabled\": true, \"dispatched\": true, \"run\": {\"id\": 88, \"html_url\": \"https://example.test/runs/88\"}}\\n'\n"
            "  exit 0\n"
            "fi\n"
            f"exec \"{real_uv}\" \"$@\"\n"
        )
        wrapper.chmod(0o755)
        return fakebin, record_path

    def init_repo(self, root: Path) -> Path:
        self.git(root, "init")
        self.git(root, "config", "user.email", "test@example.com")
        self.git(root, "config", "user.name", "tester")
        (root / "README.md").write_text("base\n")
        self.git(root, "add", "README.md")
        self.git(root, "commit", "-m", "init")
        return root

    def init_remote(self, remote: Path, seed: Path) -> None:
        self.run_cmd(["git", "init", "--bare", str(remote)], cwd=remote.parent)
        seed.mkdir()
        self.init_repo(seed)
        self.git(seed, "branch", "-M", "main")
        self.git(seed, "remote", "add", "origin", str(remote))
        self.git(seed, "push", "-u", "origin", "main")
        self.run_cmd(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)

    def clone(self, remote: Path, target: Path) -> None:
        self.run_cmd(["git", "clone", str(remote), str(target)], cwd=target.parent)

    def run_script(self, cwd: Path, *args: str, env=None, check: bool = True) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=cwd,
            env=merged_env,
            check=check,
            capture_output=True,
            text=True,
        )

    def git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run_cmd(["git", *args], cwd=cwd)

    def run_cmd(self, cmd, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
