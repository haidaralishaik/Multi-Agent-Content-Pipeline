"""
Multi-Agent Pipeline - Orchestrates all 4 agents

Research -> Write -> Edit -> Fact-Check -> Final Output
"""

from typing import TypedDict, Dict, Any, List, Optional
from dataclasses import asdict
from src.agent_core import InstructionBasedAgent
from src.cost_tracker import BedrockCostTracker
from src.tracing import PipelineTracer
from src.guardrails import ContentGuardrails, RiskLevel
from src.cache import PipelineCache
from src.evaluator import ContentEvaluator
from tools.web_search import WebSearchTool
from langgraph.graph import StateGraph, END
import logging

logger = logging.getLogger(__name__)

# Content format specifications
FORMAT_SPECS = {
    "blog_post": {
        "label": "Blog Post",
        "instruction": "Write an engaging blog post (800-1500 words)",
        "max_tokens": 3000,
    },
    "linkedin_post": {
        "label": "LinkedIn Post",
        "instruction": (
            "Write a LinkedIn post (300-500 words). Start with a strong hook line. "
            "Use short paragraphs. End with an engagement question. "
            "Use line breaks between paragraphs for readability."
        ),
        "max_tokens": 1500,
    },
    "twitter_thread": {
        "label": "Twitter/X Thread",
        "instruction": (
            "Write a Twitter/X thread of 5-7 tweets. Each tweet MUST be under 280 characters. "
            "Format as:\n\nTweet 1/N:\n[content]\n\nTweet 2/N:\n[content]\n\n"
            "Use a hook in tweet 1. End with a CTA or question."
        ),
        "max_tokens": 1000,
    },
}


class PipelineState(TypedDict):
    """
    State shared across all agents

    Each agent can read and write to this state
    """
    topic: str                    # Original topic
    content_format: str           # "blog_post", "linkedin_post", "twitter_thread"
    tone: str                     # "professional", "casual", "technical", "storytelling"
    user_notes: str               # User's custom notes/context/talking points
    research_output: str          # Researcher's output
    draft_output: str             # Writer's output
    edited_output: str            # Editor's output
    final_output: str             # The polished, fact-checked content
    fact_check_report: str        # Fact-checker's verification report (separate)
    metadata: Dict[str, Any]      # Costs, tokens, etc.
    errors: List[str]             # Any errors encountered
    _tracer: Optional[Any]        # Pipeline tracer instance (internal)
    _use_cache: bool              # Whether to use caching


class ContentPipeline:
    """
    4-agent content creation pipeline

    Orchestrates: Researcher -> Writer -> Editor -> Fact-Checker
    """

    def __init__(self):
        """Initialize pipeline with all agents"""
        logger.info("Initializing content pipeline...")

        # Create all agents
        self.researcher = InstructionBasedAgent(role='researcher')
        self.writer = InstructionBasedAgent(role='writer')
        self.editor = InstructionBasedAgent(role='editor')
        self.fact_checker = InstructionBasedAgent(role='fact_checker')

        # Web search tool (real DuckDuckGo search)
        self.web_search = WebSearchTool()

        # Cost tracker
        self.tracker = BedrockCostTracker()

        # Guardrails
        self.guardrails = ContentGuardrails()

        # Cache
        self.cache = PipelineCache()

        # Build workflow
        self.workflow = self._build_workflow()

        logger.info("Pipeline initialized with 4 agents + web search + guardrails")

    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(PipelineState)

        # Add nodes (one per agent)
        workflow.add_node("research", self._research_node)
        workflow.add_node("write", self._write_node)
        workflow.add_node("edit", self._edit_node)
        workflow.add_node("fact_check", self._fact_check_node)

        # Add edges (define flow)
        workflow.set_entry_point("research")
        workflow.add_edge("research", "write")
        workflow.add_edge("write", "edit")
        workflow.add_edge("edit", "fact_check")
        workflow.add_edge("fact_check", END)

        return workflow.compile()

    def _format_search_results(self, results: list) -> str:
        """Format web search results into readable text for agent context."""
        if not results:
            return ""

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"### Result {i}: {r.get('title', 'No title')}")
            lines.append(f"**Source:** {r.get('url', 'N/A')}")
            lines.append(f"**Snippet:** {r.get('snippet', 'No snippet')}")
            lines.append("")

        return "\n".join(lines)

    def _cache_kwargs(self, state: PipelineState) -> Dict[str, str]:
        """Build cache key kwargs from state."""
        return {
            'notes': state.get('user_notes', ''),
            'content_format': state.get('content_format', 'blog_post'),
            'tone': state.get('tone', 'professional'),
        }

    def _research_node(self, state: PipelineState) -> PipelineState:
        """Research node - gathers information using real web search"""
        logger.info("RESEARCHER starting...")
        tracer: Optional[PipelineTracer] = state.get('_tracer')

        # Cache check
        if state.get('_use_cache', True):
            cached = self.cache.get(state['topic'], "research", **self._cache_kwargs(state))
            if cached is not None:
                state['research_output'] = cached
                state['metadata']['researcher_cost'] = 0
                state['metadata']['researcher_tokens'] = {'input_tokens': 0, 'output_tokens': 0}
                state['metadata']['researcher_cached'] = True
                logger.info("RESEARCHER served from cache")
                return state

        try:
            topic = state['topic']

            # Step 1: Perform real web search
            search_results = self.web_search.search(topic, max_results=5)
            search_context = self._format_search_results(search_results)
            if tracer:
                tracer.log_tool_call("researcher", "web_search", {"query": topic, "results": len(search_results)})

            # Step 2: Build context with search results + user notes
            context = {}
            if search_context:
                context["Web Search Results"] = search_context

            user_notes = state.get('user_notes', '')
            if user_notes:
                context["User's Notes and Key Points"] = user_notes

            # Step 3: Run the researcher agent with real data
            result = self.researcher.execute(
                task=(
                    f"Research the following topic comprehensively:\n\n{topic}\n\n"
                    "Provide detailed research notes with sources. "
                    "USE the web search results provided in your context - "
                    "they contain real, current information. Cite the actual URLs."
                ),
                context=context if context else None,
                max_tokens=3000
            )

            state['research_output'] = result['output']
            state['metadata']['researcher_cost'] = result['cost']
            state['metadata']['researcher_tokens'] = result['usage']
            if tracer:
                tracer.log_llm_call("researcher", result['usage']['input_tokens'],
                                    result['usage']['output_tokens'], result['cost'])

            # Cache the result
            if state.get('_use_cache', True):
                self.cache.put(state['topic'], "research", result['output'],
                               result['cost'], **self._cache_kwargs(state))

            logger.info(f"RESEARCHER completed: ${result['cost']:.6f}")

        except Exception as e:
            logger.error(f"RESEARCHER failed: {e}")
            state['errors'].append(f"Researcher error: {str(e)}")
            state['research_output'] = f"ERROR: {str(e)}"
            if tracer:
                tracer.log_error("researcher", str(e))

        return state

    def _write_node(self, state: PipelineState) -> PipelineState:
        """Write node - creates content from research in the requested format"""
        logger.info("WRITER starting...")
        tracer: Optional[PipelineTracer] = state.get('_tracer')

        # Cache check
        if state.get('_use_cache', True):
            cached = self.cache.get(state['topic'], "write", **self._cache_kwargs(state))
            if cached is not None:
                state['draft_output'] = cached
                state['metadata']['writer_cost'] = 0
                state['metadata']['writer_tokens'] = {'input_tokens': 0, 'output_tokens': 0}
                state['metadata']['writer_cached'] = True
                logger.info("WRITER served from cache")
                return state

        try:
            content_format = state.get('content_format', 'blog_post')
            tone = state.get('tone', 'professional')
            format_spec = FORMAT_SPECS.get(content_format, FORMAT_SPECS['blog_post'])

            task = (
                f"{format_spec['instruction']} about: {state['topic']}\n\n"
                f"**Tone:** {tone}\n"
                f"**Format:** {format_spec['label']}"
            )

            result = self.writer.execute(
                task=task,
                context={
                    "Research Notes": state['research_output']
                },
                max_tokens=format_spec['max_tokens']
            )

            state['draft_output'] = result['output']
            state['metadata']['writer_cost'] = result['cost']
            state['metadata']['writer_tokens'] = result['usage']
            if tracer:
                tracer.log_llm_call("writer", result['usage']['input_tokens'],
                                    result['usage']['output_tokens'], result['cost'])

            if state.get('_use_cache', True):
                self.cache.put(state['topic'], "write", result['output'],
                               result['cost'], **self._cache_kwargs(state))

            logger.info(f"WRITER completed: ${result['cost']:.6f}")

        except Exception as e:
            logger.error(f"WRITER failed: {e}")
            state['errors'].append(f"Writer error: {str(e)}")
            state['draft_output'] = f"ERROR: {str(e)}"
            if tracer:
                tracer.log_error("writer", str(e))

        return state

    def _edit_node(self, state: PipelineState) -> PipelineState:
        """Edit node - improves content quality while preserving format and tone"""
        logger.info("EDITOR starting...")
        tracer: Optional[PipelineTracer] = state.get('_tracer')

        # Cache check
        if state.get('_use_cache', True):
            cached = self.cache.get(state['topic'], "edit", **self._cache_kwargs(state))
            if cached is not None:
                state['edited_output'] = cached
                state['metadata']['editor_cost'] = 0
                state['metadata']['editor_tokens'] = {'input_tokens': 0, 'output_tokens': 0}
                state['metadata']['editor_cached'] = True
                logger.info("EDITOR served from cache")
                return state

        try:
            tone = state.get('tone', 'professional')
            content_format = state.get('content_format', 'blog_post')
            format_spec = FORMAT_SPECS.get(content_format, FORMAT_SPECS['blog_post'])

            task = (
                f"Edit and improve the following {format_spec['label']}. "
                f"Make it clearer, more engaging, and match a {tone} tone. "
                f"Preserve the format structure."
            )

            result = self.editor.execute(
                task=task,
                context={
                    "Research Notes": state['research_output'],
                    "Draft Content": state['draft_output']
                },
                max_tokens=format_spec['max_tokens']
            )

            state['edited_output'] = result['output']
            state['metadata']['editor_cost'] = result['cost']
            state['metadata']['editor_tokens'] = result['usage']
            if tracer:
                tracer.log_llm_call("editor", result['usage']['input_tokens'],
                                    result['usage']['output_tokens'], result['cost'])

            if state.get('_use_cache', True):
                self.cache.put(state['topic'], "edit", result['output'],
                               result['cost'], **self._cache_kwargs(state))

            logger.info(f"EDITOR completed: ${result['cost']:.6f}")

        except Exception as e:
            logger.error(f"EDITOR failed: {e}")
            state['errors'].append(f"Editor error: {str(e)}")
            state['edited_output'] = state['draft_output']  # Fallback to draft
            state['metadata']['editor_degraded'] = True
            if tracer:
                tracer.log_error("editor", str(e))

        return state

    def _fact_check_node(self, state: PipelineState) -> PipelineState:
        """Fact-check node - outputs corrected content + separate verification report"""
        logger.info("FACT-CHECKER starting...")
        tracer: Optional[PipelineTracer] = state.get('_tracer')

        try:
            task = (
                "You are fact-checking the content below. Your response MUST have this EXACT structure:\n\n"
                "1. FIRST, output the COMPLETE corrected/verified version of the edited content. "
                "Copy the ENTIRE content, fixing any factual errors. If a claim cannot be verified, "
                "soften the language (e.g., 'reportedly', 'according to some sources'). "
                "Keep ALL the content structure, headings, and tone intact. "
                "Do NOT skip or summarize - output the FULL article/post.\n\n"
                "2. THEN, on its own line, output exactly: ---VERIFICATION_REPORT---\n\n"
                "3. FINALLY, output your fact-check verification report with claims verified, "
                "issues found, confidence levels, and recommendations.\n\n"
                "IMPORTANT: Section 1 must contain the COMPLETE publishable content, not a summary or plan. "
                "Start Section 1 immediately with the content - no preamble like 'I will fact-check...'."
            )

            result = self.fact_checker.execute(
                task=task,
                context={
                    "Research Notes": state['research_output'],
                    "Edited Content": state['edited_output']
                },
                max_tokens=4000
            )

            # Parse the two sections
            output = result['output']
            separator = '---VERIFICATION_REPORT---'

            if separator in output:
                parts = output.split(separator, 1)
                parsed_content = parts[0].strip()
                parsed_report = parts[1].strip()

                # Validate: if the content before separator is too short,
                # the model likely output a planning statement instead of real content.
                # Fall back to edited content in that case.
                min_length = min(len(state['edited_output']) * 0.3, 200)
                if len(parsed_content) >= min_length:
                    state['final_output'] = parsed_content
                else:
                    logger.warning(
                        f"Fact-checker content too short ({len(parsed_content)} chars), "
                        f"using edited content as final output"
                    )
                    state['final_output'] = state['edited_output']
                state['fact_check_report'] = parsed_report
            else:
                # Fallback: use edited content as final, full output as report
                state['final_output'] = state['edited_output']
                state['fact_check_report'] = output

            state['metadata']['fact_checker_cost'] = result['cost']
            state['metadata']['fact_checker_tokens'] = result['usage']
            if tracer:
                tracer.log_llm_call("fact_checker", result['usage']['input_tokens'],
                                    result['usage']['output_tokens'], result['cost'])

            logger.info(f"FACT-CHECKER completed: ${result['cost']:.6f}")

        except Exception as e:
            logger.error(f"FACT-CHECKER failed: {e}")
            state['errors'].append(f"Fact-checker error: {str(e)}")
            state['final_output'] = state['edited_output']  # Fallback to edited
            state['fact_check_report'] = f"Fact-check failed: {str(e)}"
            state['metadata']['fact_checker_degraded'] = True
            if tracer:
                tracer.log_error("fact_checker", str(e))

        return state

    def run(self, topic: str, content_format: str = "blog_post",
            tone: str = "professional", user_notes: str = "",
            use_cache: bool = True) -> Dict[str, Any]:
        """
        Run the complete pipeline

        Args:
            topic: Content topic
            content_format: "blog_post", "linkedin_post", or "twitter_thread"
            tone: "professional", "casual", "technical", or "storytelling"
            user_notes: User's own notes/key points to incorporate
            use_cache: Whether to use cached results (default True)

        Returns:
            Dict with all pipeline outputs, costs, and metadata
        """
        # Initialize tracing
        tracer = PipelineTracer()
        logger.info(f"Pipeline starting [trace_id={tracer.trace_id}] topic: {topic}")
        logger.info(f"Format: {content_format} | Tone: {tone}")

        # Input guardrails
        input_check = self.guardrails.validate_input(topic, user_notes)
        guardrail_report = {
            'input': {
                'risk_level': input_check.risk_level.value,
                'passed': input_check.passed,
                'flags': input_check.flags,
                'pii_detected': input_check.pii_detected,
            }
        }

        if not input_check.passed:
            logger.warning(f"Input blocked by guardrails: {input_check.flags}")
            return {
                'topic': topic,
                'content_format': content_format,
                'tone': tone,
                'research': '',
                'draft': '',
                'edited': '',
                'final': '',
                'fact_check_report': '',
                'total_cost': 0,
                'metadata': {},
                'errors': [f"Blocked by guardrails: {', '.join(input_check.flags)}"],
                'trace': tracer.get_summary(),
                'trace_timeline': tracer.get_timeline(),
                'guardrail_report': guardrail_report,
            }

        # Initialize state
        initial_state: PipelineState = {
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
            '_tracer': tracer,
            '_use_cache': use_cache,
        }

        # Run workflow
        final_state = self.workflow.invoke(initial_state)

        # Output guardrails - scan final content for PII
        output_check = self.guardrails.scan_output(final_state['final_output'])
        guardrail_report['output'] = {
            'risk_level': output_check.risk_level.value,
            'passed': output_check.passed,
            'flags': output_check.flags,
            'pii_detected': output_check.pii_detected,
        }
        # Auto-redact PII in final output if detected
        if output_check.pii_detected:
            final_state['final_output'] = output_check.sanitized_text

        # Quality evaluation on final content (uses Bedrock for relevancy/faithfulness)
        evaluator = ContentEvaluator(bedrock_client=self.researcher.bedrock)
        quality_score = evaluator.evaluate(
            content=final_state['final_output'],
            topic=topic,
            research=final_state['research_output'],
        )

        # Calculate total cost
        total_cost = sum([
            final_state['metadata'].get('researcher_cost', 0),
            final_state['metadata'].get('writer_cost', 0),
            final_state['metadata'].get('editor_cost', 0),
            final_state['metadata'].get('fact_checker_cost', 0)
        ])

        logger.info(f"Pipeline completed [trace_id={tracer.trace_id}]! Total cost: ${total_cost:.4f}")
        logger.info(f"Quality: grade={quality_score.grade}, overall={quality_score.overall_score}")

        # Print summary
        self.tracker.print_session_summary()

        return {
            'topic': topic,
            'content_format': content_format,
            'tone': tone,
            'research': final_state['research_output'],
            'draft': final_state['draft_output'],
            'edited': final_state['edited_output'],
            'final': final_state['final_output'],
            'fact_check_report': final_state['fact_check_report'],
            'total_cost': total_cost,
            'metadata': final_state['metadata'],
            'errors': final_state['errors'],
            'trace': tracer.get_summary(),
            'trace_timeline': tracer.get_timeline(),
            'guardrail_report': guardrail_report,
            'cache_stats': self.cache.get_stats(),
            'quality_score': quality_score.to_dict(),
        }


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    pipeline = ContentPipeline()

    result = pipeline.run(
        topic="Recent advances in RAG (Retrieval-Augmented Generation) systems",
        content_format="blog_post",
        tone="professional"
    )

    print(f"\n{'='*60}")
    print("FINAL OUTPUT")
    print(f"{'='*60}")
    print(result['final'])
    print(f"\n{'='*60}")
    print("FACT-CHECK REPORT")
    print(f"{'='*60}")
    print(result['fact_check_report'])
    print(f"\n{'='*60}")
    print(f"Total Cost: ${result['total_cost']:.4f}")
