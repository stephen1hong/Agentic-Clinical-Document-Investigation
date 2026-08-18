from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FindingOutcome(StrEnum):
    """Normalized outcome for one evaluated machine finding."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    PARTIALLY_CORRECT = "partially_correct"
    NOT_EVALUATED = "not_evaluated"


class FindingScore(BaseModel):
    """Normalized score for one machine-generated finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    outcome: FindingOutcome

    finding_type: str
    subtype: str
    severity: str

    requires_human_review: bool

    evidence_support: str | None = None

    score_value: float

    reviewer: str = ""
    rationale: str = ""


class FindingMetricSummary(BaseModel):
    """Aggregate finding-level metrics for one evaluated set."""

    model_config = ConfigDict(extra="forbid")

    total_findings: int

    evaluated_findings: int

    true_positive_count: int
    false_positive_count: int
    partially_correct_count: int
    not_evaluated_count: int

    precision: float | None = None

    false_positive_rate: float | None = None

    partial_correct_rate: float | None = None

    evaluation_coverage: float

    mean_score: float | None = None


class FindingGroupMetric(BaseModel):
    """Finding metrics for one grouping dimension/value."""

    model_config = ConfigDict(extra="forbid")

    group_name: str
    group_value: str

    summary: FindingMetricSummary


class FindingEvaluationResult(BaseModel):
    """Finding-level evaluation result for one case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str

    scores: list[FindingScore] = Field(default_factory=list)

    overall: FindingMetricSummary

    by_finding_type: list[FindingGroupMetric] = Field(default_factory=list)

    by_subtype: list[FindingGroupMetric] = Field(default_factory=list)

    by_severity: list[FindingGroupMetric] = Field(default_factory=list)

    by_review_requirement: list[FindingGroupMetric] = Field(default_factory=list)


class AggregateFindingEvaluationResult(BaseModel):
    """Aggregate finding evaluation across multiple cases."""

    model_config = ConfigDict(extra="forbid")

    case_count: int

    overall: FindingMetricSummary

    by_finding_type: list[FindingGroupMetric] = Field(default_factory=list)

    by_subtype: list[FindingGroupMetric] = Field(default_factory=list)

    by_severity: list[FindingGroupMetric] = Field(default_factory=list)

    by_review_requirement: list[FindingGroupMetric] = Field(default_factory=list)

    evaluated_case_ids: list[str] = Field(default_factory=list)
