import pytest
from datetime import datetime, timezone
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    FailureClass,
    Finding,
    ValidationContext,
    Verdict,
    SourceReliability,
    EnvironmentInfo,
    AgentInfo,
    DashboardInfo,
)
from framework.shared.profile import ProductProfile
from framework.validators.synchronization import (
    SchedulerValidator,
    QueueValidator,
    AuthenticationValidator,
    UploadValidator,
    RetryValidator,
    RecoveryValidator,
    LatencyValidator,
    SynchronizationValidator,
)

# Helpers
def build_profile(config_dict=None):
    if config_dict is None:
        config_dict = {}
    return ProductProfile(config_dict)

def build_context(evidence_list=None, minimum_layers=2):
    if evidence_list is None:
        evidence_list = []
    return ValidationContext(
        execution_id="test-run",
        environment=EnvironmentInfo(name="test-env"),
        agent=AgentInfo(),
        dashboard=DashboardInfo(),
        evidence=evidence_list,
        minimum_layers=minimum_layers,
    )

def test_scheduler_validator_no_summary():
    profile = build_profile()
    validator = SchedulerValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_scheduler_validator_not_measurable():
    profile = build_profile({
        "synchronization": {
            "thresholds": {
                "min_cycles_for_cadence": 3
            }
        }
    })
    validator = SchedulerValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 1,
            "cycle_timestamps": ["2026-07-30T12:00:00Z"]
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "cadence could not be established" in findings[0].what

def test_scheduler_validator_configured_none():
    profile = build_profile()
    validator = SchedulerValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 2,
            "cycle_timestamps": ["2026-07-30T12:00:00Z", "2026-07-30T12:01:00Z"]
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "cannot be compared with configuration" in findings[0].what

def test_scheduler_validator_healthy():
    profile = build_profile({
        "synchronization": {
            "interval_keys": {
                "upload_interval": "upload_interval_seconds"
            },
            "thresholds": {
                "min_cycles_for_cadence": 2,
                "scheduler_drift_tolerance_seconds": 10
            }
        }
    })
    validator = SchedulerValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values",
        data={"values": {"upload_interval_seconds": 60}}
    )
    runtime_ev = Evidence(
        evidence_id="EV-002",
        layer=EvidenceLayer.RUNTIME,
        source="runtime",
        summary="runtime state"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 2,
            "cycle_timestamps": ["2026-07-30T12:00:00Z", "2026-07-30T12:01:00Z"]
        }
    )
    context = build_context([config_ev, runtime_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.HEALTHY

def test_scheduler_validator_degraded():
    profile = build_profile({
        "synchronization": {
            "interval_keys": {
                "upload_interval": "upload_interval_seconds"
            },
            "thresholds": {
                "min_cycles_for_cadence": 2,
                "scheduler_drift_tolerance_seconds": 10
            }
        }
    })
    validator = SchedulerValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values",
        data={"values": {"upload_interval_seconds": 60}}
    )
    runtime_ev = Evidence(
        evidence_id="EV-002",
        layer=EvidenceLayer.RUNTIME,
        source="runtime",
        summary="runtime state"
    )
    # 120 seconds gap instead of 60 seconds
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 2,
            "cycle_timestamps": ["2026-07-30T12:00:00Z", "2026-07-30T12:02:00Z"]
        }
    )
    context = build_context([config_ev, runtime_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.DEGRADED

def test_queue_validator_no_queue():
    profile = build_profile()
    validator = QueueValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_queue_validator_inconclusive_state():
    profile = build_profile()
    validator = QueueValidator(profile)
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "absent", "error": "file missing"}
    )
    context = build_context([queue])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "state could not be observed" in findings[0].what

def test_queue_validator_exceeds_max():
    profile = build_profile({
        "synchronization": {
            "thresholds": {
                "max_queue_depth": 100
            }
        }
    })
    validator = QueueValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "present", "total_queue_depth": 101}
    )
    context = build_context([config_ev, queue])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.FAILED
    assert findings[0].failure_class == FailureClass.SYNCHRONIZATION_DEFECT

def test_queue_validator_drained():
    profile = build_profile()
    validator = QueueValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "present", "total_queue_depth": 0, "discovered_pending_tables": ["t1"]}
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={"event_count": 5, "cycle_count": 1}
    )
    context = build_context([config_ev, queue, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.HEALTHY

def test_queue_validator_empty_no_cycles():
    profile = build_profile()
    validator = QueueValidator(profile)
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "present", "total_queue_depth": 0}
    )
    context = build_context([queue])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "upload queue is empty but no upload cycle" in findings[0].what

def test_queue_validator_holds_items():
    profile = build_profile()
    validator = QueueValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "present", "total_queue_depth": 10}
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={"event_count": 5, "cycle_count": 1}
    )
    context = build_context([config_ev, queue, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.HEALTHY
    assert "holds 10 pending item" in findings[0].what

def test_queue_validator_holds_items_no_cycles():
    profile = build_profile()
    validator = QueueValidator(profile)
    queue = Evidence(
        evidence_id="EV-004",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:queue",
        summary="queue data",
        data={"state": "present", "total_queue_depth": 10}
    )
    context = build_context([queue])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE

def test_authentication_validator_no_summary():
    profile = build_profile()
    validator = AuthenticationValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_authentication_validator_with_events():
    profile = build_profile()
    validator = AuthenticationValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "events_by_pattern": {
                "auth_register": 1,
                "auth_call": 1
            }
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 2
    assert findings[0].verdict == Verdict.HEALTHY
    assert findings[1].verdict == Verdict.INCONCLUSIVE

def test_authentication_validator_no_events():
    profile = build_profile()
    validator = AuthenticationValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "events_by_pattern": {}
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 2
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert findings[1].verdict == Verdict.INCONCLUSIVE

def test_upload_validator_no_summary():
    profile = build_profile()
    validator = UploadValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_upload_validator_all_accepted():
    profile = build_profile()
    validator = UploadValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "api_calls": [{"code": "200"}, {"code": "201"}]
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.HEALTHY

def test_upload_validator_rejected():
    profile = build_profile()
    validator = UploadValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "api_calls": [{"code": "200"}, {"code": "400"}]
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.FAILED

def test_upload_validator_no_calls():
    profile = build_profile()
    validator = UploadValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "api_calls": []
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE

def test_upload_validator_skipped_channel():
    profile = build_profile()
    validator = UploadValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "api_calls": [{"code": "200"}],
            "events_by_pattern": {
                "alternate_channel_skipped": 1
            },
            "events": [
                {
                    "pattern": "alternate_channel_skipped",
                    "fields": {
                        "reason": "network busy"
                    }
                }
            ]
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 2
    assert findings[0].verdict == Verdict.HEALTHY
    assert findings[1].verdict == Verdict.DEGRADED
    assert "network busy" in findings[1].why

def test_retry_validator_no_summary():
    profile = build_profile()
    validator = RetryValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_retry_validator_no_retries():
    profile = build_profile()
    validator = RetryValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={"event_count": 0}
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE

def test_retry_validator_with_retries():
    profile = build_profile()
    validator = RetryValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 3,
            "events_by_pattern": {
                "retry": 3
            }
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.DEGRADED

def test_recovery_validator_no_evidence():
    profile = build_profile()
    validator = RecoveryValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_recovery_validator_connected():
    profile = build_profile()
    validator = RecoveryValidator(profile)
    network = Evidence(
        evidence_id="EV-005",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:network",
        summary="network values",
        data={"established_server_connections": True}
    )
    context = build_context([network])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "no loss of connectivity occurred" in findings[0].why

def test_recovery_validator_not_connected():
    profile = build_profile()
    validator = RecoveryValidator(profile)
    network = Evidence(
        evidence_id="EV-005",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:network",
        summary="network values",
        data={"established_server_connections": False}
    )
    context = build_context([network])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    assert "no offline or reconnect event" in findings[0].why

def test_latency_validator_no_summary():
    profile = build_profile()
    validator = LatencyValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_latency_validator_with_summary():
    profile = build_profile()
    validator = LatencyValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={"event_count": 1}
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE

def test_synchronization_validator_no_summary():
    profile = build_profile()
    validator = SynchronizationValidator(profile)
    context = build_context()
    findings = validator.validate(context)
    assert len(findings) == 0

def test_synchronization_validator_functioning():
    profile = build_profile()
    validator = SynchronizationValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    network = Evidence(
        evidence_id="EV-005",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:network",
        summary="network values",
        data={"established_server_connections": True}
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 2,
            "api_calls": [{"code": "200"}]
        }
    )
    context = build_context([config_ev, network, summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.HEALTHY

def test_synchronization_validator_failed():
    profile = build_profile()
    validator = SynchronizationValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 2,
            "api_calls": []
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.FAILED

def test_synchronization_validator_inconclusive():
    profile = build_profile()
    validator = SynchronizationValidator(profile)
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 0,
            "api_calls": []
        }
    )
    context = build_context([summary])
    findings = validator.validate(context)
    assert len(findings) == 1
    assert findings[0].verdict == Verdict.INCONCLUSIVE

def test_synchronization_validator_anomalies():
    profile = build_profile()
    validator = SynchronizationValidator(profile)
    config_ev = Evidence(
        evidence_id="EV-001",
        layer=EvidenceLayer.CONFIGURATION,
        source="config",
        summary="config values"
    )
    summary = Evidence(
        evidence_id="EV-003",
        layer=EvidenceLayer.SYNCHRONIZATION,
        source="synchronization:log",
        summary="log summary",
        data={
            "event_count": 5,
            "cycle_count": 0,
            "api_calls": [],
            "events_by_pattern": {
                "permission_denied": 3
            },
            "events": [
                {
                    "pattern": "queue_cleanup_result",
                    "fields": {
                        "records": "-10"
                    }
                },
                {
                    "pattern": "queue_cleanup",
                    "fields": {
                        "retention": "PLACEHOLDER"
                    }
                }
            ]
        }
    )
    context = build_context([config_ev, summary])
    findings = validator.validate(context)
    # 1 inconclusive for pipeline health, 3 anomaly findings -> 4 total
    assert len(findings) == 4
    assert findings[0].verdict == Verdict.INCONCLUSIVE
    # Check that negative record count sweep, unsubstituted placeholder, and permission denied all reported DEGRADED
    assert findings[1].verdict == Verdict.DEGRADED
    assert "negative record count" in findings[1].what
    assert findings[2].verdict == Verdict.DEGRADED
    assert "unsubstituted placeholder" in findings[2].what
    assert findings[3].verdict == Verdict.DEGRADED
    assert "could not inspect some processes" in findings[3].what
