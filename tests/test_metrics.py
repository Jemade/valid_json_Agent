from app.telemetry.metrics import MetricsCollector


def test_metrics_initial_state():
    collector = MetricsCollector()
    data = collector.get_metrics()

    assert data["total_requests"] == 0
    assert data["successful_validations"] == 0
    assert data["failed_validations"] == 0
    assert data["average_retries"] == 0.0
    assert data["retry_distribution"] == {}
    assert data["final_failure_rate"] == 0.0
    assert data["validation_failure_categories"] == {}


def test_metrics_record_success():
    collector = MetricsCollector()
    collector.record_request(attempts=1, success=True)
    collector.record_request(attempts=2, success=True)

    data = collector.get_metrics()
    assert data["total_requests"] == 2
    assert data["successful_validations"] == 2
    assert data["failed_validations"] == 0
    assert data["average_retries"] == 1.5
    assert data["retry_distribution"] == {"1": 1, "2": 1}
    assert data["final_failure_rate"] == 0.0


def test_metrics_record_failure_and_categories():
    collector = MetricsCollector()
    collector.record_attempt_failure("json_syntax")
    collector.record_attempt_failure("missing_field")
    collector.record_attempt_failure("missing_field")
    collector.record_attempt_failure("math_mismatch")
    collector.record_request(attempts=3, success=False)

    data = collector.get_metrics()
    assert data["total_requests"] == 1
    assert data["successful_validations"] == 0
    assert data["failed_validations"] == 1
    assert data["final_failure_rate"] == 1.0
    assert data["retry_distribution"] == {"3": 1}
    assert data["validation_failure_categories"] == {
        "json_syntax": 1,
        "missing_field": 2,
        "math_mismatch": 1,
    }


def test_metrics_reset():
    collector = MetricsCollector()
    collector.record_request(attempts=2, success=True)
    collector.record_attempt_failure("json_syntax")
    assert collector.get_metrics()["total_requests"] == 1

    collector.reset()
    assert collector.get_metrics()["total_requests"] == 0
    assert collector.get_metrics()["validation_failure_categories"] == {}
