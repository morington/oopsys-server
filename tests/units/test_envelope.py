from datetime import UTC, datetime

from oopsys_server.domain.envelope import ErrorReportPayload, ServerMetricsPayload
from oopsys_server.domain.enums import Severity, Source


def test_source_enum_values():
    assert Source.PROJECTS.value == "projects"
    assert {s.value for s in Source} == {"projects", "server", "docker", "agent"}


def test_error_report_payload_parses():
    payload = ErrorReportPayload.model_validate(
        {
            "severity": "critical",
            "service": "svc",
            "environment": "production",
            "exception_type": "ValueError",
            "message": "boom",
            "traceback": "tb",
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
    )
    assert payload.severity is Severity.CRITICAL
    assert payload.context == {}


def test_server_metrics_payload_optional_disk():
    payload = ServerMetricsPayload.model_validate(
        {
            "cpu_percent": 1.0,
            "mem_percent": 2.0,
            "mem_used": 1,
            "mem_total": 2,
            "net_bytes_sent": 0,
            "net_bytes_recv": 0,
            "load_1": 0.1,
            "load_5": 0.1,
            "load_15": 0.1,
            "captured_at": datetime.now(tz=UTC).isoformat(),
        }
    )
    assert payload.disk_percent is None
