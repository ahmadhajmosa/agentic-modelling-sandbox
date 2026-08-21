from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnvironmentIdentity(StrictModel):
    name: str
    version: str = "0.1"
    description: str | None = None


class Objective(StrictModel):
    description: str
    success_definition: str | None = None


class Capability(StrictModel):
    name: str
    callable: str
    description: str | None = None
    deterministic: bool = True
    tags: list[str] = Field(default_factory=list)


class ExecutionConstraints(StrictModel):
    network: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    allowed_write_paths: list[str] = Field(default_factory=lambda: ["src", "tests", "candidate.yaml"])
    allowed_commands: list[str] = Field(default_factory=lambda: ["python", "python3", "pytest"])
    max_output_chars: int = Field(default=20000, ge=100, le=1000000)
    max_file_bytes: int = Field(default=200000, ge=1, le=10000000)


class DecompositionConstraints(StrictModel):
    require_explicit_llm_boundaries: bool = True
    require_typed_contracts: bool = True
    require_end_to_end_contract: bool = True
    deterministic_calculations_testable: bool = True


class ValidationConstraints(StrictModel):
    required_checks: list[str] = Field(default_factory=list)
    # Check name -> "module:function", executed by AMS as fn(inputs, output).
    # Checks declared here are verified independently of anything the candidate
    # reports about itself.
    executable_checks: dict[str, str] = Field(default_factory=dict)


class EnvironmentConstraints(StrictModel):
    execution: ExecutionConstraints = Field(default_factory=ExecutionConstraints)
    decomposition: DecompositionConstraints = Field(default_factory=DecompositionConstraints)
    validation: ValidationConstraints = Field(default_factory=ValidationConstraints)


class DatasetSplit(StrictModel):
    train: str
    validation: str
    test: str


class EvaluationConfig(StrictModel):
    datasets: DatasetSplit
    metrics: list[str]
    minimum_score: float | None = Field(default=None, ge=0.0, le=1.0)
    protect_test_split: bool = True
    # Caps how often the protected split can be scored, so its aggregate cannot
    # be used as a tuning signal. Set to null for unlimited access.
    max_final_evaluations: int | None = Field(default=3, ge=1)


class EnvironmentManifest(StrictModel):
    schema_version: Literal["ams/v1"] = "ams/v1"
    environment: EnvironmentIdentity
    objective: Objective
    capabilities: list[Capability] = Field(default_factory=list)
    constraints: EnvironmentConstraints = Field(default_factory=EnvironmentConstraints)
    evaluation: EvaluationConfig


class IOField(StrictModel):
    name: str
    type: str
    description: str | None = None


class LLMModuleDeclaration(StrictModel):
    id: str
    implementation: str | None = None
    inputs: list[IOField] = Field(default_factory=list)
    outputs: list[IOField] = Field(default_factory=list)
    evaluation_metric: str | None = None
    optimization_target: bool = True


class DeterministicComponent(StrictModel):
    id: str
    callable: str | None = None
    responsibility: str


class DecompositionProposal(StrictModel):
    description: str | None = None
    llm_modules: list[LLMModuleDeclaration] = Field(default_factory=list)
    deterministic_components: list[DeterministicComponent] = Field(default_factory=list)
    control_flow: str


class ProposedValidation(StrictModel):
    checks: list[str] = Field(default_factory=list)


class CandidateEvaluation(StrictModel):
    end_to_end_metric: str
    module_metrics: dict[str, str] = Field(default_factory=dict)


class OptimizationDeclaration(StrictModel):
    targets: list[str] = Field(default_factory=list)
    optimizer: str | None = None
    notes: str | None = None


class ArtifactDeclaration(StrictModel):
    source_roots: list[str] = Field(default_factory=lambda: ["src"])
    test_roots: list[str] = Field(default_factory=lambda: ["tests"])
    entrypoint: str | None = None


class CandidateManifest(StrictModel):
    schema_version: Literal["ams/candidate-v1"] = "ams/candidate-v1"
    candidate_name: str
    decomposition: DecompositionProposal
    validation: ProposedValidation = Field(default_factory=ProposedValidation)
    evaluation: CandidateEvaluation
    optimization: OptimizationDeclaration = Field(default_factory=OptimizationDeclaration)
    artifacts: ArtifactDeclaration = Field(default_factory=ArtifactDeclaration)

    @model_validator(mode="after")
    def metrics_match_declared_modules(self):
        declared = {m.id for m in self.decomposition.llm_modules}
        unknown = set(self.evaluation.module_metrics) - declared
        if unknown:
            raise ValueError(f"module_metrics reference undeclared LLM modules: {sorted(unknown)}")
        return self


class ValidationIssue(StrictModel):
    severity: Literal["error", "warning"]
    rule: str
    message: str
    location: str | None = None


class ValidationReport(StrictModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
