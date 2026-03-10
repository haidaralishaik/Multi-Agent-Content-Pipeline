"""Tests for pipeline tracing"""

import time
from src.tracing import PipelineTracer, TraceEvent


def test_tracer_initialization():
    """Tracer creates a unique trace ID"""
    tracer = PipelineTracer()
    assert len(tracer.trace_id) == 8
    assert tracer.events == []

    # Two tracers get different IDs
    tracer2 = PipelineTracer()
    assert tracer.trace_id != tracer2.trace_id


def test_trace_node_context_manager():
    """trace_node records start and end events with timing"""
    tracer = PipelineTracer()

    with tracer.trace_node("researcher"):
        time.sleep(0.05)

    assert len(tracer.events) == 2
    assert tracer.events[0].event_type == "node_start"
    assert tracer.events[0].agent == "researcher"
    assert tracer.events[1].event_type == "node_end"
    assert tracer.events[1].agent == "researcher"
    assert tracer.events[1].duration_ms >= 40  # at least ~50ms


def test_trace_node_records_errors():
    """trace_node records error events when exceptions occur"""
    tracer = PipelineTracer()

    try:
        with tracer.trace_node("writer"):
            raise ValueError("test error")
    except ValueError:
        pass

    event_types = [e.event_type for e in tracer.events]
    assert "node_start" in event_types
    assert "error" in event_types
    assert "node_end" in event_types

    error_event = [e for e in tracer.events if e.event_type == "error"][0]
    assert error_event.error == "test error"


def test_log_llm_call():
    """log_llm_call records token and cost info"""
    tracer = PipelineTracer()
    tracer.log_llm_call("researcher", input_tokens=500, output_tokens=200, cost=0.001)

    assert len(tracer.events) == 1
    event = tracer.events[0]
    assert event.event_type == "llm_call"
    assert event.input_tokens == 500
    assert event.output_tokens == 200
    assert event.cost == 0.001


def test_log_tool_call():
    """log_tool_call records tool invocations"""
    tracer = PipelineTracer()
    tracer.log_tool_call("researcher", "web_search", {"query": "RAG systems"})

    assert len(tracer.events) == 1
    event = tracer.events[0]
    assert event.event_type == "tool_call"
    assert event.metadata["tool"] == "web_search"
    assert event.metadata["query"] == "RAG systems"


def test_get_summary():
    """get_summary aggregates all events"""
    tracer = PipelineTracer()

    with tracer.trace_node("researcher"):
        tracer.log_llm_call("researcher", 500, 200, 0.001)
        time.sleep(0.02)

    with tracer.trace_node("writer"):
        tracer.log_llm_call("writer", 800, 400, 0.002)
        time.sleep(0.02)

    tracer.log_error("editor", "timeout")

    summary = tracer.get_summary()
    assert summary["trace_id"] == tracer.trace_id
    assert summary["total_input_tokens"] == 1300
    assert summary["total_output_tokens"] == 600
    assert abs(summary["total_cost"] - 0.003) < 0.0001
    assert summary["error_count"] == 1
    assert "researcher" in summary["node_timings"]
    assert "writer" in summary["node_timings"]


def test_get_timeline():
    """get_timeline returns ordered events as dicts"""
    tracer = PipelineTracer()
    tracer.log_llm_call("researcher", 100, 50, 0.001)
    tracer.log_tool_call("researcher", "web_search")

    timeline = tracer.get_timeline()
    assert len(timeline) == 2
    assert isinstance(timeline[0], dict)
    assert timeline[0]["event_type"] == "llm_call"
    assert timeline[1]["event_type"] == "tool_call"
