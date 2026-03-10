"""
Pipeline Tracing - Structured observability for multi-agent pipeline

Provides trace IDs, event logging, timing, and structured output
for debugging and monitoring pipeline execution.
"""

import uuid
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class TraceEvent:
    """A single event in a pipeline trace"""
    trace_id: str
    event_type: str          # node_start, node_end, llm_call, tool_call, error, guardrail_check
    agent: str
    timestamp: str
    duration_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class PipelineTracer:
    """
    Traces pipeline execution with structured events.

    Creates a unique trace ID per run and records all events
    (node start/end, LLM calls, tool calls, errors) with timing.
    """

    def __init__(self):
        self.trace_id = str(uuid.uuid4())[:8]
        self.events: List[TraceEvent] = []
        self.start_time = time.time()
        self._node_timings: Dict[str, float] = {}

    @contextmanager
    def trace_node(self, agent: str):
        """Context manager to trace a pipeline node execution."""
        start = time.time()
        self.events.append(TraceEvent(
            trace_id=self.trace_id,
            event_type="node_start",
            agent=agent,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        logger.info(json.dumps({
            "trace_id": self.trace_id,
            "event": "node_start",
            "agent": agent,
        }))

        try:
            yield
        except Exception as e:
            self.log_error(agent, str(e))
            raise
        finally:
            duration_ms = (time.time() - start) * 1000
            self._node_timings[agent] = duration_ms
            self.events.append(TraceEvent(
                trace_id=self.trace_id,
                event_type="node_end",
                agent=agent,
                timestamp=datetime.now(timezone.utc).isoformat(),
                duration_ms=round(duration_ms, 1),
            ))
            logger.info(json.dumps({
                "trace_id": self.trace_id,
                "event": "node_end",
                "agent": agent,
                "duration_ms": round(duration_ms, 1),
            }))

    def log_llm_call(self, agent: str, input_tokens: int,
                     output_tokens: int, cost: float):
        """Record an LLM API call event."""
        self.events.append(TraceEvent(
            trace_id=self.trace_id,
            event_type="llm_call",
            agent=agent,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        ))
        logger.info(json.dumps({
            "trace_id": self.trace_id,
            "event": "llm_call",
            "agent": agent,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
        }))

    def log_tool_call(self, agent: str, tool_name: str,
                      metadata: Optional[Dict] = None):
        """Record a tool invocation event."""
        self.events.append(TraceEvent(
            trace_id=self.trace_id,
            event_type="tool_call",
            agent=agent,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"tool": tool_name, **(metadata or {})},
        ))
        logger.info(json.dumps({
            "trace_id": self.trace_id,
            "event": "tool_call",
            "agent": agent,
            "tool": tool_name,
        }))

    def log_error(self, agent: str, error: str):
        """Record an error event."""
        self.events.append(TraceEvent(
            trace_id=self.trace_id,
            event_type="error",
            agent=agent,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error=error,
        ))
        logger.error(json.dumps({
            "trace_id": self.trace_id,
            "event": "error",
            "agent": agent,
            "error": error,
        }))

    def get_summary(self) -> Dict[str, Any]:
        """Get trace summary with timings, costs, and event counts."""
        total_duration_ms = (time.time() - self.start_time) * 1000

        total_input_tokens = sum(
            e.input_tokens for e in self.events
            if e.event_type == "llm_call" and e.input_tokens
        )
        total_output_tokens = sum(
            e.output_tokens for e in self.events
            if e.event_type == "llm_call" and e.output_tokens
        )
        total_cost = sum(
            e.cost for e in self.events
            if e.event_type == "llm_call" and e.cost
        )
        error_count = sum(1 for e in self.events if e.event_type == "error")

        return {
            "trace_id": self.trace_id,
            "total_duration_ms": round(total_duration_ms, 1),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost": round(total_cost, 6),
            "event_count": len(self.events),
            "error_count": error_count,
            "node_timings": {
                agent: round(ms, 1)
                for agent, ms in self._node_timings.items()
            },
        }

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get ordered timeline of events for UI display."""
        return [asdict(e) for e in self.events]
