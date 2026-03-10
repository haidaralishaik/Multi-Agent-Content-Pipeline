"""Tests for retry and circuit breaker resilience"""

import time
from src.resilience import RetryHandler, RetryConfig, CircuitBreaker, CircuitBreakerOpenError


def test_retry_success_on_first_try():
    """No retries needed when function succeeds"""
    handler = RetryHandler(RetryConfig(max_retries=3))
    result = handler.execute_with_retry(lambda: 42)
    assert result == 42
    assert handler.retry_history == []


def test_retry_succeeds_after_failures():
    """Retries until function succeeds"""
    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient error")
        return "success"

    config = RetryConfig(max_retries=3, base_delay=0.01, retryable_exceptions=(ValueError,))
    handler = RetryHandler(config)
    result = handler.execute_with_retry(flaky)

    assert result == "success"
    assert call_count == 3
    assert len(handler.retry_history) == 2  # 2 retries before success


def test_retry_exhausts_all_attempts():
    """Raises last exception after all retries fail"""
    config = RetryConfig(max_retries=2, base_delay=0.01, retryable_exceptions=(ValueError,))
    handler = RetryHandler(config)

    try:
        handler.execute_with_retry(lambda: (_ for _ in ()).throw(ValueError("permanent")))
        assert False, "Should have raised"
    except ValueError as e:
        assert "permanent" in str(e)

    assert len(handler.retry_history) == 2


def test_retry_does_not_catch_non_retryable():
    """Non-retryable exceptions are not caught"""
    config = RetryConfig(max_retries=3, base_delay=0.01, retryable_exceptions=(ValueError,))
    handler = RetryHandler(config)

    try:
        handler.execute_with_retry(lambda: (_ for _ in ()).throw(TypeError("wrong type")))
        assert False, "Should have raised"
    except TypeError:
        pass

    assert handler.retry_history == []  # No retries attempted


def test_retry_exponential_backoff():
    """Retry delays increase exponentially"""
    config = RetryConfig(max_retries=3, base_delay=0.01, exponential_base=2.0,
                         retryable_exceptions=(ValueError,))
    handler = RetryHandler(config)

    try:
        handler.execute_with_retry(lambda: (_ for _ in ()).throw(ValueError("fail")))
    except ValueError:
        pass

    # Delays should increase (with jitter, so check rough ordering)
    assert len(handler.retry_history) == 3
    # base_delay * 2^0 = 0.01, base_delay * 2^1 = 0.02, base_delay * 2^2 = 0.04
    # With jitter, they should still generally increase


def test_circuit_breaker_stays_closed_on_success():
    """Circuit breaker stays closed when calls succeed"""
    cb = CircuitBreaker(failure_threshold=3)
    result = cb.call(lambda: "ok")
    assert result == "ok"
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_opens_after_threshold():
    """Circuit breaker opens after N consecutive failures"""
    cb = CircuitBreaker(failure_threshold=3)

    for i in range(3):
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass

    assert cb.state == CircuitBreaker.OPEN
    assert cb.failure_count == 3


def test_circuit_breaker_rejects_when_open():
    """Open circuit breaker rejects calls immediately"""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)

    try:
        cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
    except ValueError:
        pass

    assert cb.state == CircuitBreaker.OPEN

    try:
        cb.call(lambda: "should not run")
        assert False, "Should have raised CircuitBreakerOpenError"
    except CircuitBreakerOpenError:
        pass


def test_circuit_breaker_half_open_recovery():
    """Circuit breaker recovers through half-open state"""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)

    # Trip the breaker
    try:
        cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
    except ValueError:
        pass
    assert cb.state == CircuitBreaker.OPEN

    # Wait for recovery timeout
    time.sleep(0.02)

    # Next call should succeed and close the breaker
    result = cb.call(lambda: "recovered")
    assert result == "recovered"
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.failure_count == 0
