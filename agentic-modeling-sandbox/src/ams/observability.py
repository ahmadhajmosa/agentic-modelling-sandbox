from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evaluation import EvaluationError, evaluate_candidate
from .history import load_observations
from .io import load_model
from .optimization import OptimizationError, load_saved_plan
from .schemas import CandidateManifest, EnvironmentManifest
from .validation import validate_candidate, validate_source_alignment


def _all_observations(workspace: Path) -> list[dict[str, Any]]:
    return load_observations(workspace, limit=100000)


def build_summary(workspace: str | Path) -> dict[str, Any]:
    workspace = Path(workspace)
    env = load_model(workspace / 'environment.yaml', EnvironmentManifest)
    cand = load_model(workspace / 'candidate.yaml', CandidateManifest)
    obs = _all_observations(workspace)

    status_counts = Counter(o.get('status', 'unknown') for o in obs)
    action_counts = Counter(o.get('action_type', 'unknown') for o in obs)
    rule_counts = Counter((o.get('policy') or {}).get('rule', 'unknown') for o in obs if o.get('status') != 'success')

    eval_events = [o for o in obs if o.get('action_type') == 'evaluate_candidate' and o.get('status') == 'success']
    score_trend = []
    for o in eval_events:
        data = o.get('data') or {}
        if 'score' in data:
            score_trend.append({
                'timestamp': o.get('timestamp'),
                'split': data.get('split'),
                'score': data.get('score'),
                'accepted': data.get('accepted'),
            })

    manifest_validation = validate_candidate(workspace / 'environment.yaml', workspace / 'candidate.yaml')
    source_validation = validate_source_alignment(workspace)

    current_eval: dict[str, Any]
    try:
        current_eval = evaluate_candidate(workspace, split='validation', final=False)
    except (EvaluationError, FileNotFoundError, Exception) as exc:
        current_eval = {'available': False, 'error': str(exc)}

    optimization: dict[str, Any] = {'plan_exists': False}
    try:
        plan = load_saved_plan(workspace)
        optimization = {
            'plan_exists': True,
            'baseline_validation_score': plan.get('baseline', {}).get('score'),
            'targets': [t.get('id') for t in plan.get('targets', [])],
        }
    except (OptimizationError, FileNotFoundError, Exception):
        pass

    failures = []
    for o in obs:
        if o.get('status') in {'denied', 'error', 'timeout'}:
            failures.append({
                'timestamp': o.get('timestamp'),
                'action_type': o.get('action_type'),
                'status': o.get('status'),
                'rule': (o.get('policy') or {}).get('rule'),
                'message': (o.get('policy') or {}).get('message'),
                'exit_code': o.get('exit_code'),
            })

    return {
        'schema_version': 'ams/observability-summary-v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'environment': env.environment.name,
        'candidate': cand.candidate_name,
        'activity': {
            'total_actions': len(obs),
            'by_action': dict(action_counts),
            'by_status': dict(status_counts),
            'failure_rules': dict(rule_counts),
        },
        'validation': {
            'manifest_valid': manifest_validation.valid,
            'source_valid': source_validation.valid,
            'manifest_issue_count': len(manifest_validation.issues),
            'source_issue_count': len(source_validation.issues),
            'source_issues': [i.model_dump() for i in source_validation.issues],
        },
        'fitness': current_eval,
        'score_trend': score_trend,
        'optimization': optimization,
        'recent_failures': failures[-20:],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    a = summary['activity']
    v = summary['validation']
    f = summary['fitness']
    lines = [
        '# AMS Observability Report', '',
        f"**Environment:** {summary['environment']}",
        f"**Candidate:** {summary['candidate']}",
        f"**Generated:** {summary['generated_at']}", '',
        '## Executive Summary', '',
        f"- Actions observed: **{a['total_actions']}**",
        f"- Manifest validation: **{'PASS' if v['manifest_valid'] else 'FAIL'}**",
        f"- Source alignment: **{'PASS' if v['source_valid'] else 'FAIL'}**",
    ]
    if f.get('available') is False:
        lines.append(f"- Current validation fitness: **unavailable** ({f.get('error')})")
    else:
        lines.append(f"- Current validation score: **{f.get('score', 0):.4f}**")
        lines.append(f"- Environment acceptance: **{'PASS' if f.get('accepted') else 'FAIL'}**")

    lines += ['', '## Activity', '', '| Action | Count |', '|---|---:|']
    for k, n in sorted(a['by_action'].items()): lines.append(f'| `{k}` | {n} |')
    lines += ['', '### Status', '', '| Status | Count |', '|---|---:|']
    for k, n in sorted(a['by_status'].items()): lines.append(f'| {k} | {n} |')

    lines += ['', '## Evaluation Trend', '']
    if summary['score_trend']:
        lines += ['| Timestamp | Split | Score | Accepted |', '|---|---|---:|---|']
        for x in summary['score_trend']:
            lines.append(f"| {x['timestamp']} | {x['split']} | {x['score']:.4f} | {x['accepted']} |")
    else:
        lines.append('No evaluation actions have been recorded yet.')

    lines += ['', '## Validation Findings', '']
    if v['source_issues']:
        for issue in v['source_issues']:
            lines.append(f"- **{issue['severity'].upper()} — {issue['rule']}**: {issue['message']}")
    else:
        lines.append('No source-alignment issues detected.')

    lines += ['', '## Recent Failures / Denials', '']
    if summary['recent_failures']:
        for x in summary['recent_failures']:
            lines.append(f"- `{x['action_type']}` — **{x['status']}** / `{x['rule']}`: {x['message']}")
    else:
        lines.append('No failed or denied actions recorded.')

    lines += ['', '## Optimization', '']
    opt = summary['optimization']
    if opt['plan_exists']:
        lines.append(f"- Baseline validation score: **{opt.get('baseline_validation_score')}**")
        lines.append(f"- Declared optimization targets: {', '.join(opt.get('targets') or []) or 'none'}")
    else:
        lines.append('No optimization plan has been issued.')
    lines.append('')
    return '\n'.join(lines)
