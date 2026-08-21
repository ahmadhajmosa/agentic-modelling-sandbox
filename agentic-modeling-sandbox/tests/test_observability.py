import json
from pathlib import Path

from ams.io import dump_yaml
from ams.observability import build_summary, render_markdown
from ams.runtime import execute_action
from ams.templates import CANDIDATE_MODEL_TEMPLATE, CANDIDATE_TEMPLATE, ENVIRONMENT_TEMPLATE, PENSION_EVAL_TEMPLATES, PENSION_TOOL_TEMPLATES


def make_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path/'environment.yaml')
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path/'candidate.yaml')
    (tmp_path/'src').mkdir(); (tmp_path/'src/model.py').write_text(CANDIDATE_MODEL_TEMPLATE)
    (tmp_path/'tests').mkdir(); (tmp_path/'tests/test_ok.py').write_text('def test_ok(): assert True\n')
    for rel, content in PENSION_TOOL_TEMPLATES.items():
        p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
    for rel, rows in PENSION_EVAL_TEMPLATES.items():
        p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r)+'\n' for r in rows))


def test_summary_aggregates_actions_and_eval(tmp_path):
    make_workspace(tmp_path)
    execute_action(tmp_path, {'type':'read_file','path':'src/model.py'})
    execute_action(tmp_path, {'type':'evaluate_candidate','split':'validation','final':False})
    s=build_summary(tmp_path)
    assert s['activity']['total_actions'] == 2
    assert s['activity']['by_action']['evaluate_candidate'] == 1
    assert s['fitness']['score'] == 1.0
    assert len(s['score_trend']) == 1


def test_summary_includes_failures(tmp_path):
    make_workspace(tmp_path)
    execute_action(tmp_path, {'type':'write_file','path':'environment.yaml','content':'bad'})
    s=build_summary(tmp_path)
    assert s['activity']['by_status']['denied'] == 1
    assert s['recent_failures'][0]['rule'] == 'WRITE_PATH_POLICY'


def test_markdown_report(tmp_path):
    make_workspace(tmp_path)
    s=build_summary(tmp_path)
    md=render_markdown(s)
    assert '# AMS Observability Report' in md
    assert 'Current validation score' in md
