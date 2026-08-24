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


def _control_flow_ids(control_flow: str) -> list[str]:
    for separator in ('->', '|', '+', ','):
        control_flow = control_flow.replace(separator, '->')
    return [part.strip() for part in control_flow.split('->') if part.strip()]


def _mermaid_label(value: Any) -> str:
    text = str(value).replace('"', "'").replace('\n', ' ')
    return text[:120] + '...' if len(text) > 120 else text


def _component_summary(cand: CandidateManifest) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    for module in cand.decomposition.llm_modules:
        components[module.id] = {
            'id': module.id,
            'kind': 'llm',
            'implementation': module.implementation,
            'signature': None,
            'inputs': [field.name for field in module.inputs],
            'outputs': [field.name for field in module.outputs],
            'evaluation_metric': module.evaluation_metric or cand.evaluation.module_metrics.get(module.id),
            'optimization_target': module.optimization_target,
        }
    for component in cand.decomposition.deterministic_components:
        components[component.id] = {
            'id': component.id,
            'kind': 'deterministic',
            'implementation': component.implementation,
            'signature': component.signature,
            'inputs': [field.name for field in component.inputs],
            'outputs': [field.name for field in component.outputs],
            'evaluation_metric': None,
            'optimization_target': False,
        }

    ordered_ids = _control_flow_ids(cand.decomposition.control_flow)
    if not ordered_ids:
        ordered_ids = list(components)

    return {
        'description': cand.decomposition.description,
        'control_flow': cand.decomposition.control_flow,
        'ordered_ids': ordered_ids,
        'components': list(components.values()),
    }


def _timeline(obs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, item in enumerate(obs, start=1):
        data = item.get('data') or {}
        policy = item.get('policy') or {}
        event = {
            'step': index,
            'timestamp': item.get('timestamp'),
            'agent_action': item.get('action_type', 'unknown'),
            'ams_response': item.get('status', 'unknown'),
            'rule': policy.get('rule'),
            'message': policy.get('message'),
        }
        if item.get('action_type') == 'evaluate_candidate':
            event.update({
                'split': data.get('split'),
                'score': data.get('score'),
                'accepted': data.get('accepted'),
            })
        elif item.get('action_type') in {'run_command', 'run_tests'}:
            event['exit_code'] = item.get('exit_code')
        events.append(event)
    return events


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
        'interaction_timeline': _timeline(obs),
        'composition': _component_summary(cand),
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

    lines += ['', '## Agent/AMS Interaction Timeline', '']
    timeline = summary.get('interaction_timeline') or []
    if timeline:
        lines += ['```mermaid', 'sequenceDiagram', '    participant Agent as AI agent', '    participant AMS as AMS environment']
        for event in timeline[-12:]:
            action = _mermaid_label(event.get('agent_action', 'action'))
            status = _mermaid_label(event.get('ams_response', 'response'))
            rule = event.get('rule')
            detail = f"{status} / {rule}" if rule else status
            if event.get('split') is not None:
                detail += f" / {event.get('split')} score {event.get('score', 0):.4f}"
            lines.append(f'    Agent->>AMS: {action}')
            lines.append(f'    AMS-->>Agent: {_mermaid_label(detail)}')
        lines += ['```', '']
        lines += ['| Step | Time | Agent action | AMS response | Evidence |', '|---:|---|---|---|---|']
        for event in timeline[-12:]:
            evidence = event.get('rule') or ''
            if event.get('split') is not None:
                evidence = f"{event.get('split')} score {event.get('score', 0):.4f}, accepted={event.get('accepted')}"
            elif event.get('exit_code') is not None:
                evidence = f"exit_code={event.get('exit_code')}"
            lines.append(
                f"| {event.get('step')} | {event.get('timestamp')} | "
                f"`{event.get('agent_action')}` | **{event.get('ams_response')}** | {evidence} |"
            )
    else:
        lines.append('No AMS actions have been recorded yet.')

    lines += ['', '## Composition Graph', '']
    composition = summary.get('composition') or {}
    components = {c['id']: c for c in composition.get('components', [])}
    ordered = composition.get('ordered_ids') or list(components)
    if components:
        lines += ['```mermaid', 'flowchart LR']
        previous = None
        for component_id in ordered:
            component = components.get(component_id, {'id': component_id, 'kind': 'unknown'})
            kind = 'LLM boundary' if component.get('kind') == 'llm' else component.get('kind', 'unknown')
            impl = component.get('implementation') or component.get('signature') or ''
            label = _mermaid_label(f"{component_id}\\n{kind}\\n{impl}")
            lines.append(f'    {component_id}["{label}"]')
            if previous:
                lines.append(f'    {previous} --> {component_id}')
            previous = component_id
        lines += ['```', '']
        lines += ['| Component | Kind | Implementation | Signature | Inputs | Outputs |', '|---|---|---|---|---|---|']
        for component in composition.get('components', []):
            lines.append(
                f"| `{component['id']}` | {component['kind']} | "
                f"{component.get('implementation') or ''} | {component.get('signature') or ''} | "
                f"{', '.join(component.get('inputs') or []) or '-'} | "
                f"{', '.join(component.get('outputs') or []) or '-'} |"
            )
        if composition.get('control_flow'):
            lines += ['', f"Declared control flow: `{composition['control_flow']}`"]
    else:
        lines.append('No declared decomposition components found.')

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
