"""Unit tests for retry, circuit breaker, structured logger, and track_tokens."""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.metrics import TokenUsageRecord, CostCalculator


# --- @with_retry decorator ---


@pytest.mark.asyncio
async def test_retry_success_on_first_attempt_returns_result_no_retry():
    from src.utils.retry import with_retry
    call_count = 0
    @with_retry(max_attempts=3, base_delay=0.01, max_delay=1.0, exception_types=(ValueError,))
    async def succeed():
        nonlocal call_count
        call_count += 1
        return 42
    result = await succeed()
    assert result == 42
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_transient_error_on_first_attempt_retries():
    from src.utils.retry import with_retry
    call_count = 0
    @with_retry(max_attempts=3, base_delay=0.01, max_delay=1.0, exception_types=(ValueError,))
    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("transient")
        return 42
    with patch("src.utils.retry.structured_logger"):
        result = await fail_then_succeed()
    assert result == 42
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_success_on_second_attempt_returns_result():
    from src.utils.retry import with_retry
    call_count = 0
    @with_retry(max_attempts=3, base_delay=0.01, max_delay=1.0, exception_types=(OSError,))
    async def fail_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("retry")
        return "ok"
    with patch("src.utils.retry.structured_logger"):
        result = await fail_once()
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_three_consecutive_failures_raises_original_exception_type():
    from src.utils.retry import with_retry
    @with_retry(max_attempts=3, base_delay=0.01, max_delay=1.0, exception_types=(ValueError,))
    async def always_fail():
        raise ValueError("nope")
    with patch("src.utils.retry.structured_logger"):
        with pytest.raises(ValueError, match="nope"):
            await always_fail()


@pytest.mark.asyncio
async def test_retry_delay_between_attempt_1_and_2_at_least_base_delay():
    from src.utils.retry import with_retry
    base_delay = 0.1
    delays = []
    async def capture_sleep(secs):
        delays.append(secs)
    call_count = 0
    @with_retry(max_attempts=3, base_delay=base_delay, max_delay=10.0, exception_types=(ValueError,))
    async def fail_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("x")
        return 1
    with patch("src.utils.retry.structured_logger"), patch("asyncio.sleep", side_effect=capture_sleep):
        await fail_once()
    assert len(delays) >= 1
    assert delays[0] >= base_delay


@pytest.mark.asyncio
async def test_retry_delay_between_attempt_2_and_3_at_least_base_delay_times_two():
    from src.utils.retry import with_retry
    base_delay = 0.1
    delays = []
    async def capture_sleep(secs):
        delays.append(secs)
    call_count = 0
    @with_retry(max_attempts=3, base_delay=base_delay, max_delay=10.0, exception_types=(ValueError,))
    async def fail_three_times():
        nonlocal call_count
        call_count += 1
        raise ValueError("x")
    with patch("src.utils.retry.structured_logger"), patch("asyncio.sleep", side_effect=capture_sleep):
        with pytest.raises(ValueError):
            await fail_three_times()
    assert len(delays) >= 2
    assert delays[1] >= base_delay * 2


@pytest.mark.asyncio
async def test_retry_non_specified_exception_propagates_immediately_without_retry():
    from src.utils.retry import with_retry
    call_count = 0
    @with_retry(max_attempts=3, base_delay=0.01, exception_types=(ValueError,))
    async def raise_type_error():
        nonlocal call_count
        call_count += 1
        raise TypeError("not retried")
    with pytest.raises(TypeError, match="not retried"):
        await raise_type_error()
    assert call_count == 1


# --- Circuit breaker state machine ---


def test_circuit_breaker_initial_state_closed():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_five_consecutive_failures_transitions_to_open():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    for _ in range(5):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_circuit_breaker_four_consecutive_failures_remains_closed():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    for _ in range(4):
        cb.record_failure()
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_open_rejects_immediately_raises_circuit_open_error():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
    cb = CircuitBreaker("gemini")
    for _ in range(5):
        cb.record_failure()
    with pytest.raises(CircuitOpenError):
        cb.check_can_attempt()


def test_circuit_breaker_after_cooldown_transitions_to_half_open():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=100.0):
        for _ in range(5):
            cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=161.0):
        cb.check_can_attempt()
    assert cb.state == CircuitState.HALF_OPEN


def test_circuit_breaker_success_in_half_open_transitions_to_closed():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=100.0):
        for _ in range(5):
            cb.record_failure()
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=161.0):
        cb.check_can_attempt()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_failure_in_half_open_transitions_back_to_open():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    cb = CircuitBreaker("gemini")
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=100.0):
        for _ in range(5):
            cb.record_failure()
    with patch("src.utils.circuit_breaker.time.monotonic", return_value=161.0):
        cb.check_can_attempt()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_circuit_breaker_successful_call_resets_consecutive_failure_count():
    from src.utils.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker("gemini")
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb._consecutive_failures == 0


# --- Circuit breaker service isolation ---


def test_circuit_breaker_gemini_opening_does_not_affect_claude():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    gemini = CircuitBreaker("gemini")
    claude = CircuitBreaker("claude")
    for _ in range(5):
        gemini.record_failure()
    assert gemini.state == CircuitState.OPEN
    assert claude.state == CircuitState.CLOSED


def test_circuit_breaker_claude_opening_does_not_affect_database():
    from src.utils.circuit_breaker import CircuitBreaker, CircuitState
    claude = CircuitBreaker("claude")
    db = CircuitBreaker("database")
    for _ in range(5):
        claude.record_failure()
    assert claude.state == CircuitState.OPEN
    assert db.state == CircuitState.CLOSED


def test_circuit_breaker_each_service_has_independent_failure_count():
    from src.utils.circuit_breaker import CircuitBreaker
    a = CircuitBreaker("gemini")
    b = CircuitBreaker("claude")
    a.record_failure()
    a.record_failure()
    b.record_failure()
    assert a._consecutive_failures == 2
    assert b._consecutive_failures == 1


# --- Structured logger ---


def test_structured_logger_ad_published_includes_ad_id_and_final_score():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("ad_published", ad_id="ad-1", final_score=7.5, total_attempts=2, total_cost_usd=0.01)
        with open(path) as f:
            line = f.read().strip()
        data = json.loads(line)
        assert data["event"] == "ad_published"
        assert data["ad_id"] == "ad-1"
        assert data["final_score"] == 7.5
    finally:
        Path(path).unlink(missing_ok=True)


def test_structured_logger_ad_abandoned_includes_failure_pattern():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("ad_abandoned", ad_id="ad-1", brief_id="b-1", failure_pattern="oscillation", total_attempts=7)
        with open(path) as f:
            data = json.loads(f.read().strip())
        assert data["failure_pattern"] == "oscillation"
    finally:
        Path(path).unlink(missing_ok=True)


def test_structured_logger_api_error_includes_service_error_type_error_message():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("api_error", service="gemini", error_type="RateLimitError", error_message="429", attempt_number=1)
        with open(path) as f:
            data = json.loads(f.read().strip())
        assert data["service"] == "gemini"
        assert data["error_type"] == "RateLimitError"
        assert data["error_message"] == "429"
    finally:
        Path(path).unlink(missing_ok=True)


def test_structured_logger_all_events_include_timestamp_iso8601():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("batch_started", run_id="r1", total_briefs=10)
        with open(path) as f:
            data = json.loads(f.read().strip())
        assert "timestamp" in data
        assert "T" in data["timestamp"]
    finally:
        Path(path).unlink(missing_ok=True)


def test_structured_logger_all_events_include_level():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("circuit_breaker_closed", service="gemini")
        with open(path) as f:
            data = json.loads(f.read().strip())
        assert "level" in data
    finally:
        Path(path).unlink(missing_ok=True)


def test_structured_logger_each_entry_valid_json():
    from src.utils.logger import structured_logger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        path = f.name
    try:
        with patch("src.utils.logger.get_settings") as mock_settings:
            mock_settings.return_value.log_file_path = path
            structured_logger.log("ratchet_would_trigger", current_threshold=7.0, avg_score=8.0, window_size=10)
        with open(path) as f:
            line = f.read().strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)
    finally:
        Path(path).unlink(missing_ok=True)


# --- @track_tokens decorator ---


@pytest.mark.asyncio
async def test_track_tokens_gemini_call_produces_record_with_operation_generation():
    from src.utils.tracking import track_tokens
    records = []
    def persist(record: TokenUsageRecord):
        records.append(record)
    mock_response = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 100
    mock_response.usage_metadata.candidates_token_count = 50
    @track_tokens(operation="generation", model="gemini-1.5-flash", provider="google", persist_callback=persist)
    async def call_gemini(ad_id, brief_id):
        return mock_response
    await call_gemini("ad-1", "brief-1")
    assert len(records) == 1
    assert records[0].operation == "generation"


@pytest.mark.asyncio
async def test_track_tokens_claude_call_produces_record_with_operation_evaluation():
    from src.utils.tracking import track_tokens
    records = []
    def persist(record: TokenUsageRecord):
        records.append(record)
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 200
    mock_response.usage.output_tokens = 100
    @track_tokens(operation="evaluation", model="claude-sonnet-4-6", provider="anthropic", persist_callback=persist)
    async def call_claude(ad_id, brief_id):
        return mock_response
    await call_claude("ad-1", "brief-1")
    assert len(records) == 1
    assert records[0].operation == "evaluation"


@pytest.mark.asyncio
async def test_track_tokens_cost_usd_matches_cost_calculator():
    from src.utils.tracking import track_tokens
    records = []
    def persist(record: TokenUsageRecord):
        records.append(record)
    mock_response = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 1_000_000
    mock_response.usage_metadata.candidates_token_count = 0
    @track_tokens(operation="generation", model="gemini-1.5-flash", provider="google", persist_callback=persist)
    async def call_gemini(ad_id, brief_id):
        return mock_response
    await call_gemini("ad-1", "brief-1")
    expected = CostCalculator.calculate("google", "gemini-1.5-flash", 1_000_000, 0)
    assert abs(records[0].cost_usd - expected) < 0.0001


@pytest.mark.asyncio
async def test_track_tokens_input_output_tokens_match_mock_response():
    from src.utils.tracking import track_tokens
    records = []
    def persist(record: TokenUsageRecord):
        records.append(record)
    mock_response = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 111
    mock_response.usage_metadata.candidates_token_count = 222
    @track_tokens(operation="generation", model="gemini-1.5-flash", provider="google", persist_callback=persist)
    async def call_gemini(ad_id, brief_id):
        return mock_response
    await call_gemini("ad-1", "brief-1")
    assert records[0].input_tokens == 111
    assert records[0].output_tokens == 222
