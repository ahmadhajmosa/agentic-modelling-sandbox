from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io import load_model
from .schemas import CandidateManifest


DSPY_LM_CONSTRUCTORS = {
    "Predict",
    "ChainOfThought",
    "ReAct",
    "RLM",
    "CodeAct",
    "ProgramOfThought",
    "MultiChainComparison",
}


@dataclass
class DiscoveredBoundary:
    id: str
    implementation: str
    file: str
    line: int
    signature: str | None = None
    owner_class: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "implementation": self.implementation,
            "file": self.file,
            "line": self.line,
            "signature": self.signature,
            "owner_class": self.owner_class,
        }


@dataclass
class DiscoveredSignature:
    name: str
    file: str
    line: int
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }


@dataclass
class DiscoveredModule:
    name: str
    file: str
    line: int
    signature: str | None = None
    forward_inputs: list[str] = field(default_factory=list)
    has_forward: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "id": _snake_case(node_name=self.name),
            "file": self.file,
            "line": self.line,
            "signature": self.signature,
            "forward_inputs": self.forward_inputs,
            "has_forward": self.has_forward,
        }


def _snake_case(*, node_name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(node_name):
        if char.isupper() and index > 0 and (not node_name[index - 1].isupper()):
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _constructor_name(call: ast.Call) -> str | None:
    dotted = _dotted_name(call.func)
    if not dotted:
        return None
    return dotted.split(".")[-1]


def _signature_arg(call: ast.Call) -> str | None:
    if call.args:
        return _dotted_name(call.args[0]) or (call.args[0].value if isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str) else None)
    for kw in call.keywords:
        if kw.arg == "signature":
            return _dotted_name(kw.value) or (kw.value.value if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) else None)
    return None


def _target_id(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        # self.interpret -> interpret; object.child -> child
        return node.attr
    return None


def _assignment_value_name(stmt: ast.stmt, target_name: str) -> str | None:
    target: ast.AST | None = None
    value: ast.AST | None = None
    if isinstance(stmt, ast.Assign):
        for candidate in stmt.targets:
            if _target_id(candidate) == target_name:
                target = candidate
                value = stmt.value
                break
    elif isinstance(stmt, ast.AnnAssign):
        if _target_id(stmt.target) == target_name:
            target = stmt.target
            value = stmt.value
    if target is None or value is None:
        return None
    return _dotted_name(value) or (
        value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
    )


class DSPyVisitor(ast.NodeVisitor):
    def __init__(self, rel_file: str):
        self.rel_file = rel_file
        self.class_stack: list[str] = []
        self.boundaries: list[DiscoveredBoundary] = []
        self.signatures: list[DiscoveredSignature] = []
        self.modules: list[DiscoveredModule] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = {_dotted_name(b) for b in node.bases}
        is_signature = any(b and b.split(".")[-1] == "Signature" for b in bases)
        is_module = any(b and b.split(".")[-1] == "Module" for b in bases)
        if is_signature:
            inputs: list[str] = []
            outputs: list[str] = []
            for stmt in node.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
                    name = _target_id(target)
                    value = stmt.value
                    if not name or not isinstance(value, ast.Call):
                        continue
                    field_ctor = _constructor_name(value)
                    if field_ctor == "InputField":
                        inputs.append(name)
                    elif field_ctor == "OutputField":
                        outputs.append(name)
            self.signatures.append(DiscoveredSignature(
                name=node.name,
                file=self.rel_file,
                line=node.lineno,
                inputs=inputs,
                outputs=outputs,
            ))

        if is_module:
            signature: str | None = None
            forward_inputs: list[str] = []
            has_forward = False
            for stmt in node.body:
                signature = signature or _assignment_value_name(stmt, "signature")
                if isinstance(stmt, ast.FunctionDef):
                    if stmt.name == "__init__":
                        for nested in ast.walk(stmt):
                            if isinstance(nested, (ast.Assign, ast.AnnAssign)):
                                signature = signature or _assignment_value_name(nested, "signature")
                    elif stmt.name == "forward":
                        has_forward = True
                        forward_inputs = [
                            arg.arg for arg in stmt.args.args if arg.arg != "self"
                        ]
            self.modules.append(DiscoveredModule(
                name=node.name,
                file=self.rel_file,
                line=node.lineno,
                signature=signature,
                forward_inputs=forward_inputs,
                has_forward=has_forward,
            ))

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _maybe_boundary(self, target: ast.AST, value: ast.AST):
        if not isinstance(value, ast.Call):
            return
        ctor = _constructor_name(value)
        if ctor not in DSPY_LM_CONSTRUCTORS:
            return
        boundary_id = _target_id(target)
        if not boundary_id:
            return
        self.boundaries.append(DiscoveredBoundary(
            id=boundary_id,
            implementation=f"dspy.{ctor}",
            file=self.rel_file,
            line=value.lineno,
            signature=_signature_arg(value),
            owner_class=self.class_stack[-1] if self.class_stack else None,
        ))

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._maybe_boundary(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self._maybe_boundary(node.target, node.value)
        self.generic_visit(node)


def inspect_candidate(workspace: str | Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    cand = load_model(workspace / "candidate.yaml", CandidateManifest)

    files: list[Path] = []
    for root_name in cand.artifacts.source_roots:
        source_root = (workspace / root_name).resolve()
        try:
            source_root.relative_to(workspace)
        except ValueError:
            continue
        if source_root.is_file() and source_root.suffix == ".py":
            files.append(source_root)
        elif source_root.exists():
            files.extend(p for p in source_root.rglob("*.py") if ".ams" not in p.parts)

    boundaries: list[DiscoveredBoundary] = []
    signatures: list[DiscoveredSignature] = []
    modules: list[DiscoveredModule] = []
    parse_errors: list[dict[str, Any]] = []

    for path in sorted(set(files)):
        rel = str(path.relative_to(workspace))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append({"file": rel, "error": str(exc)})
            continue
        visitor = DSPyVisitor(rel)
        visitor.visit(tree)
        boundaries.extend(visitor.boundaries)
        signatures.extend(visitor.signatures)
        modules.extend(visitor.modules)

    return {
        "files_scanned": len(set(files)),
        "boundaries": [b.as_dict() for b in boundaries],
        "signatures": [s.as_dict() for s in signatures],
        "modules": [m.as_dict() for m in modules],
        "parse_errors": parse_errors,
    }
