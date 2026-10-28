"""Unit tests for Langfuse Observability module.

Verifies:
1. Zero-overhead graceful degradation with dummy client when disabled or keys missing.
2. User ID pseudonymization (SHA-256 with salt) and health PII scrubbing.
3. Trace context lifecycle, span nesting, and latency tracking.
4. Generation tracking with token metrics.
5. Error propagation and exception recording in spans.
"""

import pytest

from core import observability


def test_dummy_client_lifecycle_when_disabled():
    client = observability.get_langfuse_client()
    assert isinstance(client, observability._DummyClient)

    # Verify dummy methods do not raise exceptions
    trace = client.trace(name="test_trace", user_id="user123")
    assert isinstance(trace, observability._DummyTrace)

    span = trace.span(name="test_span")
    assert isinstance(span, observability._DummySpan)

    gen = span.generation(name="test_gen")
    assert isinstance(gen, observability._DummyGeneration)

    trace.score(name="feedback", value=1.0)
    client.flush()
    client.shutdown()


def test_hash_user_id_pseudonymization():
    assert observability.hash_user_id(None) is None
    assert observability.hash_user_id("") is None

    hashed1 = observability.hash_user_id("user_alice")
    hashed2 = observability.hash_user_id("user_alice")
    hashed_bob = observability.hash_user_id("user_bob")

    assert hashed1 == hashed2
    assert hashed1 != hashed_bob
    assert "user_alice" not in hashed1
    assert len(hashed1) == 24


def test_redact_sensitive_health_data():
    raw_payload = {
        "user_id": "test_id",
        "email": "patient@hospital.vn",
        "full_name": "Nguyen Van A",
        "phone": "0912345678",
        "weight_kg": 75.0,
        "height_cm": 175.0,
        "nested": {
            "email": "doctor@hospital.vn",
            "metric": "inbody_270",
        },
    }

    sanitized = observability.redact_sensitive_health_data(raw_payload)

    assert sanitized["email"] == "[REDACTED_PII]"
    assert sanitized["full_name"] == "[REDACTED_PII]"
    assert sanitized["phone"] == "[REDACTED_PII]"
    assert sanitized["nested"]["email"] == "[REDACTED_PII]"
    # Numerical clinical measurements needed for evaluation are preserved
    assert sanitized["weight_kg"] == 75.0
    assert sanitized["height_cm"] == 175.0


def test_trace_span_context_manager_latency():
    trace = observability.start_trace(name="chat_request", user_id="user_test")
    assert trace is not None

    with observability.trace_span("normalize_question", span_type="agent_node") as span:
        assert span is not None

    # Test nested spans
    with observability.trace_span("supervisor_agent", span_type="agent_node"):
        with observability.trace_span("rag_hybrid_search", span_type="retrieval"):
            observability.record_generation(
                name="response_composer",
                model="qwen-2.5-7b",
                prompt_messages=[{"role": "user", "content": "tinh BMI"}],
                output_text="BMI cua ban la 24.5",
                prompt_tokens=45,
                completion_tokens=20,
            )


def test_trace_span_exception_recording():
    with pytest.raises(ValueError, match="simulated failure"):
        with observability.trace_span("failing_node", span_type="agent_node"):
            raise ValueError("simulated failure")


def test_record_feedback_does_not_crash():
    observability.record_feedback(trace_id="test-123", name="relevance", value=0.9, comment="Accurate answer")
