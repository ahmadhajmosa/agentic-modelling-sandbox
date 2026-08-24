from __future__ import annotations

import json
from pathlib import Path
import typer
from pydantic import ValidationError

from .io import dump_yaml, load_model
from .schemas import CandidateManifest, EnvironmentManifest
from .templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE, PENSION_TOOL_TEMPLATES, PENSION_EVAL_TEMPLATES, CANDIDATE_MODEL_TEMPLATE
from .validation import validate_candidate, validate_source_alignment
from .runtime import execute_action
from .history import load_observations
from .capabilities import describe_capability
from .evaluation import EvaluationError
from .dspy_inspector import inspect_candidate
from .optimization import OptimizationError, optimization_plan, save_optimization_plan, verify_optimization
from .discovery import overview, topic_help, schema_document, examples_for, guide
from .observability import build_summary, render_markdown

app = typer.Typer(
    help="Agentic Modeling Sandbox (AMS): an LLM-free environment for external agents building modeling programs.",
    epilog="Start with `ams help` or `ams guide`. Use --json for machine-readable discovery and operational output.",
    no_args_is_help=True,
)


def emit(data, as_json: bool):
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, str):
            typer.echo(data)
        else:
            typer.echo(json.dumps(data, indent=2, default=str))


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing manifest files"),
):
    path.mkdir(parents=True, exist_ok=True)
    env_path = path / "environment.yaml"
    cand_path = path / "candidate.yaml"
    for target, payload in [(env_path, ENVIRONMENT_TEMPLATE), (cand_path, CANDIDATE_TEMPLATE)]:
        if target.exists() and not force:
            raise typer.BadParameter(f"{target} already exists; use --force to overwrite")
        dump_yaml(payload, target)
    (path / "src").mkdir(exist_ok=True)
    (path / "tests").mkdir(exist_ok=True)
    (path / "evals").mkdir(exist_ok=True)
    for rel_path, content in PENSION_TOOL_TEMPLATES.items():
        target = path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or force:
            target.write_text(content, encoding="utf-8")
    model_target = path / "src/model.py"
    if not model_target.exists() or force:
        model_target.write_text(CANDIDATE_MODEL_TEMPLATE, encoding="utf-8")
    for rel_path, rows in PENSION_EVAL_TEMPLATES.items():
        target = path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or force:
            target.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    typer.echo(f"Initialized AMS workspace at {path}")


@app.command()
def state(
    path: Path = typer.Argument(Path(".")),
    json_output: bool = typer.Option(False, "--json"),
):
    try:
        env = load_model(path / "environment.yaml", EnvironmentManifest)
        cand = load_model(path / "candidate.yaml", CandidateManifest)
        report = validate_candidate(path / "environment.yaml", path / "candidate.yaml")
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)

    data = {
        "environment": env.environment.model_dump(),
        "objective": env.objective.model_dump(),
        "candidate": cand.candidate_name,
        "capabilities": [c.model_dump() for c in env.capabilities],
        "validation": report.model_dump(),
    }
    emit(data, json_output)


@app.command()
def rules(
    path: Path = typer.Argument(Path(".")),
    json_output: bool = typer.Option(False, "--json"),
):
    try:
        env = load_model(path / "environment.yaml", EnvironmentManifest)
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit({
        "constraints": env.constraints.model_dump(),
        "evaluation": env.evaluation.model_dump(),
    }, json_output)


@app.command()
def capabilities(
    path: Path = typer.Argument(Path(".")),
    json_output: bool = typer.Option(False, "--json"),
):
    try:
        env = load_model(path / "environment.yaml", EnvironmentManifest)
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit([describe_capability(path, c) for c in env.capabilities], json_output)


@app.command()
def validate(
    path: Path = typer.Argument(Path(".")),
    json_output: bool = typer.Option(False, "--json"),
    source: bool = typer.Option(False, "--source", help="Also inspect candidate DSPy source and compare it with candidate.yaml"),
):
    report = validate_source_alignment(path) if source else validate_candidate(path / "environment.yaml", path / "candidate.yaml")
    emit(report.model_dump(), json_output)
    if not report.valid:
        raise typer.Exit(1)




@app.command("help")
def help_command(
    topic: str | None = typer.Argument(None, help="Concept: environment, candidate, actions, decomposition, contracts, evaluation, optimization, dspy"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
):
    """Explain AMS concepts and the recommended agent workflow."""
    try:
        payload = topic_help(topic) if topic else overview()
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(payload, json_output)


@app.command("schema")
def schema_command(
    artifact: str = typer.Argument(..., help="environment, candidate, action, observation, validation, evaluation, optimization-plan"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON Schema as JSON"),
):
    """Return the fixed machine-readable schema for an AMS artifact/protocol."""
    try:
        payload = schema_document(artifact)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(payload, json_output)


@app.command("examples")
def examples_command(
    topic: str = typer.Argument("workflow", help="workflow, action, or decomposition"),
    json_output: bool = typer.Option(False, "--json", help="Emit examples as JSON"),
):
    """Return non-prescriptive examples for agents integrating with AMS."""
    try:
        payload = examples_for(topic)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(payload, json_output)


@app.command("guide")
def guide_command(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
):
    """Return a deterministic next-step recommendation based on current workspace state."""
    emit(guide(path), json_output)


@app.command("test")
def test_command(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    json_output: bool = typer.Option(False, "--json", help="Emit the structured observation as JSON"),
):
    """Run the environment-approved default test command."""
    observation = execute_action(path, {"type": "run_tests"})
    emit(observation.model_dump(), json_output)
    if observation.status in {"denied", "error", "timeout"} or observation.exit_code not in {0, None}:
        raise typer.Exit(1)



@app.command("summary")
def summary_command(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    json_output: bool = typer.Option(False, "--json", help="Emit observability summary as JSON"),
):
    """Summarize AMS activity, validation, fitness, failures, and optimization state."""
    try:
        payload = build_summary(path)
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(payload, json_output)


@app.command("report")
def report_command(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write Markdown report to this path"),
    json_output: bool = typer.Option(False, "--json", help="Emit summary JSON instead of Markdown"),
):
    """Generate a human-readable evidence and observability report."""
    try:
        payload = build_summary(path)
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    if json_output:
        emit(payload, True)
        return
    report = render_markdown(payload)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(report)


@app.command("inspect-dspy")
def inspect_dspy(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Statically discover DSPy signatures and LM boundaries without importing candidate code."""
    try:
        report = inspect_candidate(path)
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(report, json_output)


@app.command("act")
def act(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    request: Path = typer.Argument(..., help="JSON action file, or '-' for stdin"),
    json_output: bool = typer.Option(False, "--json"),
):
    try:
        if str(request) == "-":
            raw = json.load(typer.get_text_stream("stdin"))
        else:
            raw = json.loads(request.read_text(encoding="utf-8"))
        observation = execute_action(path, raw)
    except (ValidationError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(observation.model_dump(), json_output)
    if observation.status in {"denied", "error", "timeout"}:
        raise typer.Exit(1)


@app.command("observations")
def observations(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    limit: int = typer.Option(20, "--limit", min=1, max=1000),
    json_output: bool = typer.Option(False, "--json"),
):
    emit(load_observations(path, limit=limit), json_output)


@app.command("eval")
def evaluate(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    split: str = typer.Option("validation", "--split", help="train, validation, or test"),
    final: bool = typer.Option(False, "--final", help="Authorize protected held-out evaluation"),
    json_output: bool = typer.Option(False, "--json"),
):
    if split not in {"train", "validation", "test"}:
        raise typer.BadParameter("--split must be train, validation, or test")
    # Routed through the action protocol so direct CLI evaluations are recorded
    # in .ams/history.jsonl and appear in observability score trends.
    try:
        observation = execute_action(path, {"type": "evaluate_candidate", "split": split, "final": final})
    except (ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    if observation.status != "success":
        typer.echo(observation.policy.message, err=True)
        raise typer.Exit(2)
    report = observation.data
    emit(report, json_output)
    if not report["accepted"]:
        raise typer.Exit(1)



@app.command("optimization-plan")
def optimization_plan_cmd(
    path: Path = typer.Argument(Path("."), help="Workspace directory"),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist immutable baseline/fingerprints under .ams"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Issue the protocol an external optimizer must follow."""
    try:
        plan = optimization_plan(path)
        if save:
            save_optimization_plan(path, plan)
    except (OptimizationError, EvaluationError, ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(plan, json_output)


@app.command("verify-optimization")
def verify_optimization_cmd(
    path: Path = typer.Argument(Path("."), help="Workspace containing the optimized candidate"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Independently verify an externally optimized candidate."""
    try:
        report = verify_optimization(path)
    except (OptimizationError, EvaluationError, ValidationError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    emit(report, json_output)
    if not report["accepted"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
