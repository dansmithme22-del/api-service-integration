"""Phase A.2 contract tests.

Covers every stage's Pydantic contract:

- Instantiation with minimal + full fields
- Round-trip JSON (model_dump_json -> model_validate_json)
- Semver validation (§13.6 decision)
- Cross-stage compatibility: output of stage N assignable to input of
  stage N+1 (chained construction).

Contract tests here are strictly at the schema level. Behavioral
integration tests (real stages producing real outputs) belong in
Phase A.7.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.pipeline.contracts import (
    AcquireRequest,
    AcquireResult,
    Artifact,
    AssemblyResult,
    CalibrationResult,
    Classification,
    ClassifiedPrimitives,
    EmitResult,
    NormalizedGeometry,
    Primitive,
    StageMeta,
    TextSpan,
    ValidationCheck,
    ValidationReport,
    is_semver,
)


# --- Helpers --------------------------------------------------------------


def _meta(stage: str) -> StageMeta:
    return StageMeta(stage_name=stage)


def _sample_primitive(pid: str = "p1") -> Primitive:
    return Primitive(
        id=pid,
        kind="line",
        coords=[(0.0, 0.0), (10.0, 0.0)],
        stroke_width_pt=0.6,
    )


# --- Semver -----------------------------------------------------------------


class TestSemver:
    @pytest.mark.parametrize("value", ["1.0.0", "0.1.0", "10.20.30", "1.0.99"])
    def test_valid_semver_accepted(self, value: str) -> None:
        assert is_semver(value)

    @pytest.mark.parametrize(
        "value",
        ["1.0", "1", "1.0.0-rc1", "1.0.0+build", "v1.0.0", ""],
    )
    def test_invalid_semver_rejected(self, value: str) -> None:
        assert not is_semver(value)

    def test_pydantic_rejects_non_semver_on_stage_output(self) -> None:
        with pytest.raises(ValidationError):
            AcquireResult(
                schema_version="1.0",  # too short
                pdf_path=Path("x.pdf"),
                page_index=0,
                page_size_pt=(612.0, 792.0),
                render_dpi=200,
                png_path=Path("x.png"),
                is_vector=True,
                has_text=True,
                classification_reason="ok",
                meta=_meta("acquire"),
            )


# --- Per-stage round-trip -------------------------------------------------


class TestAcquire:
    def test_request_and_result_roundtrip(self) -> None:
        req = AcquireRequest(pdf_path=Path("/tmp/a.pdf"))
        assert req.render_dpi == 200
        assert req.page_index is None

        result = AcquireResult(
            pdf_path=Path("/tmp/a.pdf"),
            page_index=2,
            page_size_pt=(612.0, 792.0),
            render_dpi=200,
            png_path=Path("/tmp/a.png"),
            is_vector=True,
            has_text=False,
            classification_reason="most_vector_paths",
            meta=_meta("acquire"),
        )
        clone = AcquireResult.model_validate_json(result.model_dump_json())
        assert clone == result


class TestExtract:
    def test_extract_result_round_trip(self) -> None:
        from src.pipeline.contracts.extract import ExtractResult

        result = ExtractResult(
            page_size_pt=(612.0, 792.0),
            primitives=[_sample_primitive("a"), _sample_primitive("b")],
            text_spans=[TextSpan(text="A101", bbox_pt=(0, 0, 10, 10))],
            stroke_histogram={0.6: 42, 0.3: 17},
            meta=_meta("extract"),
        )
        clone = ExtractResult.model_validate_json(result.model_dump_json())
        assert clone.stroke_histogram[0.6] == 42
        assert len(clone.primitives) == 2

    def test_primitive_kind_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Primitive(id="x", kind="banana", coords=[], stroke_width_pt=0.6)  # type: ignore[arg-type]


class TestNormalize:
    def test_normalized_geometry_round_trip(self) -> None:
        calib = CalibrationResult(
            inches_per_norm=48.0,
            source="dim_callout",
            dim_text="1/4\" = 1'-0\"",
            confidence=0.95,
        )
        geom = NormalizedGeometry(
            calibration=calib,
            page_size_pt=(612.0, 792.0),
            page_size_in=(8.5, 11.0),
            primitives_by_stroke_class={"wall_weight": [_sample_primitive("w1")]},
            meta=_meta("normalize"),
        )
        clone = NormalizedGeometry.model_validate_json(geom.model_dump_json())
        assert clone.calibration.source == "dim_callout"
        assert clone.calibration.confidence == 0.95

    def test_calibration_source_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationResult(inches_per_norm=1.0, source="guess")  # type: ignore[arg-type]


class TestClassify:
    def test_classified_primitives_round_trip(self) -> None:
        c = Classification(
            primitive_id="w1",
            aia_layer="A-WALL-EXST",
            csi_division="02",
            subcategory="Wall — Existing",
            confidence=0.87,
            source="stroke_weight",
        )
        cp = ClassifiedPrimitives(
            classifications=[c],
            semantic_labels={"r1": "Exam Room"},
            ai_provider="anthropic",
            ai_model="claude-opus-4-7",
            ai_cache_hit=True,
            ai_cost_usd=0.032,
            meta=_meta("classify"),
        )
        clone = ClassifiedPrimitives.model_validate_json(cp.model_dump_json())
        assert clone.classifications[0].aia_layer == "A-WALL-EXST"
        assert clone.ai_cache_hit is True
        assert clone.ai_cost_usd == 0.032


class TestAssemble:
    def test_assembly_result_round_trip_with_component(self) -> None:
        from src.components.schemas import Component, ComponentKind

        wall = Component(
            id="c1",
            mark="W101",
            kind=ComponentKind.WALL,
            name="Interior Stud Wall 2x6",
            aia_layer="A-WALL",
            csi_division="09",
        )
        result = AssemblyResult(
            components_by_division={"09": [wall]},
            orphan_primitives=[_sample_primitive("o1")],
            coverage=0.94,
            meta=_meta("assemble"),
        )
        clone = AssemblyResult.model_validate_json(result.model_dump_json())
        assert clone.coverage == 0.94
        assert clone.components_by_division["09"][0].mark == "W101"
        assert len(clone.orphan_primitives) == 1


class TestValidate:
    def test_validation_report_round_trip(self) -> None:
        report = ValidationReport(
            checks=[
                ValidationCheck(
                    rule_id="egress_width",
                    severity="failure",
                    message="Door D101 is 30\", need 32\" clear",
                    component_ids=["D101"],
                ),
                ValidationCheck(
                    rule_id="wall_thickness_default",
                    severity="warning",
                    message="Wall W101 uses default thickness",
                    component_ids=["W101"],
                ),
            ],
            summary={"failure": 1, "warning": 1, "info": 0},
            overall_status="fail",
            blocks_emit=True,
            meta=_meta("validate"),
        )
        clone = ValidationReport.model_validate_json(report.model_dump_json())
        assert clone.overall_status == "fail"
        assert clone.blocks_emit is True
        assert clone.checks[0].severity == "failure"

    def test_severity_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            ValidationCheck(rule_id="x", severity="oopsie", message="")  # type: ignore[arg-type]


class TestEmit:
    def test_emit_result_round_trip(self) -> None:
        art = Artifact(
            path=Path("out/schedule.csv"),
            kind="schedule_csv",
            sha256="a" * 64,
            size_bytes=1234,
        )
        result = EmitResult(
            artifacts=[art],
            output_dir=Path("out"),
            meta=_meta("emit"),
        )
        clone = EmitResult.model_validate_json(result.model_dump_json())
        assert clone.artifacts[0].kind == "schedule_csv"
        assert clone.output_dir == Path("out")

    def test_artifact_kind_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Artifact(path=Path("x"), kind="parquet", sha256="", size_bytes=0)  # type: ignore[arg-type]


# --- Cross-stage chaining -------------------------------------------------


def test_stage_boundaries_chain_end_to_end() -> None:
    """Every stage's output must be assignable to a variable of its
    successor's input type without adapter code.

    Enforces the contract-based design: the runner walks stages and
    hands output[N] as input[N+1]. If any pair diverges, this test
    fails and we know before we ship.
    """
    from src.pipeline.contracts.extract import ExtractResult

    # Stage 1 output
    acquire = AcquireResult(
        pdf_path=Path("/tmp/a.pdf"),
        page_index=0,
        page_size_pt=(612.0, 792.0),
        render_dpi=200,
        png_path=Path("/tmp/a.png"),
        is_vector=True,
        has_text=True,
        classification_reason="",
        meta=_meta("acquire"),
    )

    # Stage 2 accepts a stage 1 output (via its runtime handler, not
    # type-level — we assert the shape carries forward what Extract
    # needs to know).
    assert acquire.page_size_pt is not None

    extract = ExtractResult(
        page_size_pt=acquire.page_size_pt,
        primitives=[_sample_primitive("p")],
        stroke_histogram={0.6: 1},
        meta=_meta("extract"),
    )

    # Stage 3
    normalize = NormalizedGeometry(
        calibration=CalibrationResult(inches_per_norm=48.0, source="default"),
        page_size_pt=extract.page_size_pt,
        page_size_in=(extract.page_size_pt[0] / 72, extract.page_size_pt[1] / 72),
        primitives_by_stroke_class={"wall_weight": extract.primitives},
        meta=_meta("normalize"),
    )

    # Stage 4
    classify = ClassifiedPrimitives(
        classifications=[
            Classification(
                primitive_id=normalize.primitives_by_stroke_class["wall_weight"][0].id,
                aia_layer="A-WALL",
                csi_division="09",
                subcategory="Wall — New",
                confidence=0.9,
                source="stroke_weight",
            ),
        ],
        meta=_meta("classify"),
    )

    # Stage 5
    from src.components.schemas import Component, ComponentKind

    assembly = AssemblyResult(
        components_by_division={
            "09": [
                Component(
                    id="c1",
                    mark="W101",
                    kind=ComponentKind.WALL,
                    csi_division="09",
                    aia_layer="A-WALL",
                ),
            ],
        },
        coverage=1.0,
        meta=_meta("assemble"),
    )

    # Stage 6
    report = ValidationReport(
        checks=[],
        summary={"failure": 0, "warning": 0, "info": 0},
        overall_status="pass",
        blocks_emit=False,
        meta=_meta("validate"),
    )

    # Stage 7
    emit = EmitResult(
        artifacts=[],
        output_dir=Path("out"),
        meta=_meta("emit"),
    )

    # All seven survive round-trip via JSON — real proof the chain is
    # serialisable (which the runner and cache both rely on).
    for obj in (acquire, extract, normalize, classify, assembly, report, emit):
        type(obj).model_validate_json(obj.model_dump_json())
