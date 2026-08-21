import copy
import pytest
from pydantic import ValidationError

from ams.schemas import EnvironmentManifest, CandidateManifest
from ams.templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE


def test_environment_template_valid():
    env = EnvironmentManifest.model_validate(ENVIRONMENT_TEMPLATE)
    assert env.schema_version == "ams/v1"


def test_candidate_template_valid():
    cand = CandidateManifest.model_validate(CANDIDATE_TEMPLATE)
    assert cand.schema_version == "ams/candidate-v1"


def test_candidate_cannot_override_environment_fields():
    data = copy.deepcopy(CANDIDATE_TEMPLATE)
    data["constraints"] = {"evaluation": {"minimum_score": 0.1}}
    with pytest.raises(ValidationError):
        CandidateManifest.model_validate(data)


def test_candidate_rejects_metric_for_undeclared_module():
    data = copy.deepcopy(CANDIDATE_TEMPLATE)
    data["evaluation"]["module_metrics"]["ghost"] = "accuracy"
    with pytest.raises(ValidationError):
        CandidateManifest.model_validate(data)
