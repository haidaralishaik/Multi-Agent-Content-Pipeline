"""
Interactive Pipeline - Human-in-the-loop review between stages

Extends ContentPipeline to support step-by-step execution where
a human can review, edit, or re-run each agent's output before
passing it to the next stage.
"""

from typing import Dict, Any, Optional
from src.pipeline import ContentPipeline, PipelineState
from src.tracing import PipelineTracer
from src.evaluator import ContentEvaluator
import logging

logger = logging.getLogger(__name__)


class InteractivePipeline(ContentPipeline):
    """
    Pipeline that supports human-in-the-loop review between stages.

    Instead of running the full LangGraph workflow, runs one stage
    at a time and allows human review/edit between stages.
    """

    STAGES = ["research", "write", "edit", "fact_check"]

    STAGE_OUTPUT_FIELDS = {
        "research": "research_output",
        "write": "draft_output",
        "edit": "edited_output",
        "fact_check": "final_output",
    }

    def __init__(self):
        super().__init__()

    def create_initial_state(self, topic: str, content_format: str = "blog_post",
                             tone: str = "professional",
                             user_notes: str = "") -> PipelineState:
        """Create the initial pipeline state for interactive mode."""
        return {
            'topic': topic,
            'content_format': content_format,
            'tone': tone,
            'user_notes': user_notes,
            'research_output': '',
            'draft_output': '',
            'edited_output': '',
            'final_output': '',
            'fact_check_report': '',
            'metadata': {},
            'errors': [],
            '_tracer': PipelineTracer(),
            '_use_cache': True,
        }

    def run_stage(self, stage: str, state: PipelineState) -> PipelineState:
        """
        Run a single pipeline stage.

        Args:
            stage: One of "research", "write", "edit", "fact_check"
            state: Current pipeline state

        Returns:
            Updated pipeline state
        """
        node_map = {
            "research": self._research_node,
            "write": self._write_node,
            "edit": self._edit_node,
            "fact_check": self._fact_check_node,
        }

        if stage not in node_map:
            raise ValueError(f"Unknown stage: {stage}. Must be one of {self.STAGES}")

        logger.info(f"Interactive mode: running stage '{stage}'")
        node_func = node_map[stage]
        return node_func(state)

    def inject_human_edit(self, state: PipelineState, stage: str,
                          edited_content: str,
                          feedback: str = "") -> PipelineState:
        """
        Inject human-edited content into the pipeline state.

        Args:
            state: Current pipeline state
            stage: Which stage's output to replace
            edited_content: The human-edited text
            feedback: Optional feedback on why it was edited

        Returns:
            Updated pipeline state
        """
        field = self.STAGE_OUTPUT_FIELDS.get(stage)
        if not field:
            raise ValueError(f"Unknown stage: {stage}")

        state[field] = edited_content
        state['metadata'][f'{stage}_human_edited'] = True
        if feedback:
            state['metadata'][f'{stage}_human_feedback'] = feedback

        logger.info(f"Human edit injected for stage '{stage}' ({len(edited_content)} chars)")
        return state

    def get_stage_output(self, state: PipelineState, stage: str) -> str:
        """Get the output text for a given stage."""
        field = self.STAGE_OUTPUT_FIELDS.get(stage)
        if not field:
            raise ValueError(f"Unknown stage: {stage}")
        return state.get(field, '')

    def build_result(self, state: PipelineState) -> Dict[str, Any]:
        """Build the final result dict from interactive state (same format as run())."""
        tracer: Optional[PipelineTracer] = state.get('_tracer')

        # Quality evaluation (uses Bedrock for relevancy/faithfulness)
        evaluator = ContentEvaluator(bedrock_client=self.researcher.bedrock)
        quality_score = evaluator.evaluate(
            content=state['final_output'],
            topic=state['topic'],
            research=state['research_output'],
        )

        total_cost = sum([
            state['metadata'].get('researcher_cost', 0),
            state['metadata'].get('writer_cost', 0),
            state['metadata'].get('editor_cost', 0),
            state['metadata'].get('fact_checker_cost', 0),
        ])

        return {
            'topic': state['topic'],
            'content_format': state.get('content_format', 'blog_post'),
            'tone': state.get('tone', 'professional'),
            'research': state['research_output'],
            'draft': state['draft_output'],
            'edited': state['edited_output'],
            'final': state['final_output'],
            'fact_check_report': state['fact_check_report'],
            'total_cost': total_cost,
            'metadata': state['metadata'],
            'errors': state['errors'],
            'trace': tracer.get_summary() if tracer else {},
            'trace_timeline': tracer.get_timeline() if tracer else [],
            'guardrail_report': {},
            'cache_stats': self.cache.get_stats() if hasattr(self, 'cache') else {},
            'quality_score': quality_score.to_dict(),
        }
