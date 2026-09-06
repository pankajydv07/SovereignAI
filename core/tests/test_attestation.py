"""Unit tests for offline attestation and operational metrics engine."""

import pytest
from audit.attestation import AttestationEngine


def test_attestation_report_generation(tmp_path):
    """Test generating signed attestation report."""
    # Create fake rules directory
    rules_dir = tmp_path / ".agents" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "00-sovereignty.md").write_text("# Sovereignty Rule\nNo egress.")
    (rules_dir / "10-architecture.md").write_text("# Architecture Boundary\nJSON-RPC over stdio.")

    engine = AttestationEngine(workspace_root=tmp_path)
    report = engine.generate_attestation_report(egress_count=0)

    assert report.is_air_gapped is True
    assert report.egress_count == 0
    assert len(report.interface_inventory) == 3
    assert len(report.active_rulesets) == 2
    assert len(report.attestation_sha256) == 64
    assert report.routing_table["coder"] == "qwen3-coder:30b"


def test_operational_metrics():
    """Test operational metrics carry required sample size N and measurement date."""
    engine = AttestationEngine()
    metrics = engine.get_operational_metrics()

    assert len(metrics) >= 7
    for m in metrics:
        assert m.sample_size > 0
        assert m.measured_date != ""
        assert m.value != ""
        assert m.name != ""
