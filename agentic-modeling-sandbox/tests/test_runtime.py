import copy
from pathlib import Path

from ams.io import dump_yaml
from ams.runtime import execute_action
from ams.templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE
from ams.history import load_observations


def setup_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()


def test_write_file_allowed(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "write_file",
        "path": "src/model.py",
        "content": "VALUE = 42\n",
    })
    assert obs.status == "success"
    assert (tmp_path / "src/model.py").read_text() == "VALUE = 42\n"
    assert obs.artifacts_changed == ["src/model.py"]


def test_write_file_outside_allowed_roots_denied(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "write_file",
        "path": "environment.yaml",
        "content": "hacked: true\n",
    })
    assert obs.status == "denied"
    assert obs.policy.rule == "WRITE_PATH_POLICY"


def test_path_traversal_denied(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "write_file",
        "path": "../escape.py",
        "content": "x=1\n",
    })
    assert obs.status == "denied"
    assert not (tmp_path.parent / "escape.py").exists()


def test_allowed_command_executes(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["python", "-c", "print(2 + 3)"],
    })
    assert obs.status == "success"
    assert obs.stdout.strip() == "5"
    assert obs.exit_code == 0


def test_unapproved_command_denied(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["sh", "-c", "echo nope"],
    })
    assert obs.status == "denied"
    assert obs.policy.rule == "COMMAND_ALLOWLIST"


def test_read_file_returns_structured_content(tmp_path):
    setup_workspace(tmp_path)
    (tmp_path / "src/example.py").write_text("abc\n", encoding="utf-8")
    obs = execute_action(tmp_path, {
        "type": "read_file",
        "path": "src/example.py",
    })
    assert obs.status == "success"
    assert obs.data["content"] == "abc\n"


def test_subprocess_cannot_lower_its_own_acceptance_threshold(tmp_path):
    setup_workspace(tmp_path)
    original = (tmp_path / "environment.yaml").read_text(encoding="utf-8")
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["python", "-c", "open('environment.yaml','a').write('\\nhacked: true\\n')"],
    })
    assert obs.status == "denied"
    assert obs.policy.rule == "ENVIRONMENT_INTEGRITY"
    assert (tmp_path / "environment.yaml").read_text(encoding="utf-8") == original
    assert "environment.yaml" in obs.data["restored_paths"]


def test_subprocess_cannot_add_files_outside_allowed_roots(tmp_path):
    setup_workspace(tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools/recon.py").write_text("ORIGINAL = 1\n", encoding="utf-8")
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["python", "-c", "open('tools/extra.py','w').write('X = 1\\n')"],
    })
    assert obs.status == "denied"
    assert obs.policy.rule == "ENVIRONMENT_INTEGRITY"
    assert not (tmp_path / "tools/extra.py").exists()


def test_subprocess_may_write_inside_allowed_roots(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["python", "-c", "open('src/generated.py','w').write('X = 1\\n')"],
    })
    assert obs.status == "success"
    assert (tmp_path / "src/generated.py").read_text(encoding="utf-8") == "X = 1\n"


def test_missing_executable_returns_observation_instead_of_raising(tmp_path):
    setup_workspace(tmp_path)
    manifest = copy.deepcopy(ENVIRONMENT_TEMPLATE)
    manifest["constraints"]["execution"]["allowed_commands"] = ["ams-nonexistent-binary"]
    dump_yaml(manifest, tmp_path / "environment.yaml")
    obs = execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["ams-nonexistent-binary", "--version"],
    })
    assert obs.status == "error"
    assert obs.policy.rule == "COMMAND_NOT_FOUND"
    assert "ams-nonexistent-binary" in obs.policy.message
    assert load_observations(tmp_path)[-1]["action_type"] == "run_command"


def test_run_tests_can_import_candidate_workspace_modules(tmp_path):
    setup_workspace(tmp_path)
    (tmp_path / "src/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/model.py").write_text("VALUE = 42\n", encoding="utf-8")
    (tmp_path / "tests/test_candidate.py").write_text(
        "from src.model import VALUE\n\n\ndef test_value():\n    assert VALUE == 42\n",
        encoding="utf-8",
    )
    obs = execute_action(tmp_path, {"type": "run_tests"})
    assert obs.status == "success", obs.stdout + obs.stderr
    assert obs.exit_code == 0


def test_observation_history_is_persisted(tmp_path):
    setup_workspace(tmp_path)
    execute_action(tmp_path, {
        "type": "write_file",
        "path": "src/model.py",
        "content": "x = 1\n",
    })
    execute_action(tmp_path, {
        "type": "run_command",
        "argv": ["python", "-c", "print('ok')"],
    })
    history = load_observations(tmp_path)
    assert len(history) == 2
    assert history[0]["action_type"] == "write_file"
    assert history[1]["action_type"] == "run_command"
