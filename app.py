"""
Streamlit UI for Multi-Agent Content Pipeline

Create blog posts, LinkedIn posts, and Twitter threads
using 4 specialized AI agents on AWS Bedrock.

Features: Guardrails, quality scoring, caching, tracing, human-in-the-loop review.
"""

import streamlit as st
from src.pipeline import ContentPipeline
from src.pipeline_interactive import InteractivePipeline
from pathlib import Path
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Page config
st.set_page_config(
    page_title="Multi-Agent Content Pipeline",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'pipeline' not in st.session_state:
    st.session_state.pipeline = None
if 'interactive_pipeline' not in st.session_state:
    st.session_state.interactive_pipeline = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'total_spent' not in st.session_state:
    st.session_state.total_spent = 0.0
# Interactive mode state
if 'interactive_stage' not in st.session_state:
    st.session_state.interactive_stage = -1  # -1 = not started
if 'interactive_state' not in st.session_state:
    st.session_state.interactive_state = None

# Sidebar
with st.sidebar:
    st.title("🤖 Content Pipeline")
    st.caption("4 specialized agents working together")

    st.divider()

    st.subheader("The Team")
    st.markdown("""
    1. 🔍 **Researcher** - Searches the web & gathers info
    2. ✍️ **Writer** - Creates content in your format
    3. 📝 **Editor** - Improves quality & clarity
    4. 🔎 **Fact-Checker** - Verifies accuracy
    """)

    st.divider()

    st.subheader("💰 Cost Tracking")
    st.metric("Session Total", f"${st.session_state.total_spent:.4f}")

    if st.session_state.last_result:
        st.metric("Last Run", f"${st.session_state.last_result['total_cost']:.4f}")

    st.caption("~$0.01-0.03 per content piece")

    st.divider()

    st.subheader("Settings")
    use_cache = st.checkbox("Use Cache", value=True, help="Reuse cached results for repeated topics")

    if st.button("🗑️ Clear Cache"):
        if st.session_state.pipeline:
            count = st.session_state.pipeline.cache.clear()
            st.success(f"Cleared {count} cached entries")
        else:
            st.info("No pipeline initialized yet")

    st.divider()

    if st.button("🔄 Reset Session"):
        st.session_state.pipeline = None
        st.session_state.interactive_pipeline = None
        st.session_state.last_result = None
        st.session_state.total_spent = 0.0
        st.session_state.interactive_stage = -1
        st.session_state.interactive_state = None
        st.rerun()

# Main area
st.title("🚀 AI Content Creator")
st.markdown("**Enter a topic, pick your format, and let 4 AI agents create polished content!**")

# Pipeline mode selection
mode = st.radio(
    "Pipeline Mode",
    ["Automatic (Full Pipeline)", "Interactive (Review Each Stage)"],
    horizontal=True,
    help="Interactive mode lets you review and edit each agent's output before passing it to the next"
)

# Topic input
topic = st.text_area(
    "What do you want to write about?",
    placeholder="Example: How RAG systems are transforming enterprise search in 2024",
    height=100
)

# Format and tone selection
col_format, col_tone = st.columns(2)

with col_format:
    content_format = st.selectbox(
        "Content Format",
        options=["blog_post", "linkedin_post", "twitter_thread"],
        format_func=lambda x: {
            "blog_post": "📝 Blog Post (800-1500 words)",
            "linkedin_post": "💼 LinkedIn Post (300-500 words)",
            "twitter_thread": "🐦 Twitter/X Thread (5-7 tweets)",
        }[x],
        index=0
    )

with col_tone:
    tone = st.selectbox(
        "Tone",
        options=["professional", "casual", "technical", "storytelling"],
        format_func=lambda x: {
            "professional": "👔 Professional",
            "casual": "😎 Casual / Conversational",
            "technical": "🔧 Technical",
            "storytelling": "📖 Storytelling",
        }[x],
        index=0
    )

# User notes
user_notes = st.text_area(
    "Your Notes / Key Points (optional)",
    placeholder="Paste your own notes, talking points, data, or perspective here.",
    height=120
)

# ==========================
# AUTOMATIC MODE
# ==========================
if mode == "Automatic (Full Pipeline)":
    col1, col2 = st.columns([1, 4])
    with col1:
        run_button = st.button("🚀 Create Content", type="primary", disabled=not topic)
    with col2:
        if topic:
            st.caption("Estimated cost: $0.01-0.03 | Time: ~60-90 seconds")

    if run_button and topic:
        if not st.session_state.pipeline:
            with st.spinner("Initializing agents..."):
                st.session_state.pipeline = ContentPipeline()

        st.subheader("📊 Pipeline Progress")
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("🔍 Searching the web & researching your topic...")
            progress_bar.progress(0.1)

            result = st.session_state.pipeline.run(
                topic=topic,
                content_format=content_format,
                tone=tone,
                user_notes=user_notes,
                use_cache=use_cache,
            )

            # Check for guardrail blocks
            if result.get('errors') and any('guardrails' in e.lower() for e in result['errors']):
                progress_bar.progress(1.0)
                status_text.text("🚫 Blocked by guardrails")
                st.error(f"Input blocked: {result['errors'][0]}")
            else:
                st.session_state.last_result = result
                st.session_state.total_spent += result['total_cost']

                progress_bar.progress(1.0)
                status_text.text("✅ Pipeline complete!")

                # Save to outputs
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = Path('outputs') / f"content_{timestamp}.json"
                output_file.parent.mkdir(exist_ok=True)

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                format_label = {"blog_post": "Blog Post", "linkedin_post": "LinkedIn Post", "twitter_thread": "Twitter Thread"}
                st.success(f"✅ {format_label.get(content_format, 'Content')} created! Cost: ${result['total_cost']:.4f}")

        except Exception as e:
            st.error(f"❌ Pipeline failed: {str(e)}")
            st.exception(e)

# ==========================
# INTERACTIVE MODE
# ==========================
elif mode == "Interactive (Review Each Stage)":
    stages = InteractivePipeline.STAGES
    stage_labels = {
        "research": "🔍 Researcher",
        "write": "✍️ Writer",
        "edit": "📝 Editor",
        "fact_check": "🔎 Fact-Checker",
    }
    current = st.session_state.interactive_stage

    # Progress indicator
    cols = st.columns(4)
    for i, stage in enumerate(stages):
        with cols[i]:
            if i < current:
                st.success(f"{stage_labels[stage]} ✓")
            elif i == current:
                st.info(f"{stage_labels[stage]} ◄")
            else:
                st.empty()
                st.caption(f"{stage_labels[stage]}")

    # Start button
    if current == -1:
        if st.button("🚀 Start Interactive Pipeline", type="primary", disabled=not topic):
            if not st.session_state.interactive_pipeline:
                with st.spinner("Initializing agents..."):
                    st.session_state.interactive_pipeline = InteractivePipeline()

            state = st.session_state.interactive_pipeline.create_initial_state(
                topic=topic, content_format=content_format,
                tone=tone, user_notes=user_notes,
            )
            st.session_state.interactive_state = state
            st.session_state.interactive_stage = 0
            st.rerun()

    # Run current stage
    elif current < len(stages):
        stage = stages[current]
        pipeline = st.session_state.interactive_pipeline
        state = st.session_state.interactive_state

        # Run stage if output is empty
        output_field = InteractivePipeline.STAGE_OUTPUT_FIELDS[stage]
        if not state.get(output_field):
            with st.spinner(f"Running {stage_labels[stage]}..."):
                state = pipeline.run_stage(stage, state)
                st.session_state.interactive_state = state

        # Show output for review
        output_text = pipeline.get_stage_output(state, stage)
        st.subheader(f"Review: {stage_labels[stage]} Output")

        edited = st.text_area(
            "Review and edit (or approve as-is):",
            value=output_text, height=400,
            key=f"edit_{stage}",
        )

        feedback = st.text_input(
            "Feedback (optional - why you edited this):",
            key=f"feedback_{stage}",
        )

        col_approve, col_rerun, col_restart = st.columns(3)

        with col_approve:
            if st.button("✅ Approve & Continue", key=f"approve_{stage}"):
                if edited != output_text:
                    pipeline.inject_human_edit(state, stage, edited, feedback)
                st.session_state.interactive_stage = current + 1
                st.rerun()

        with col_rerun:
            if st.button("🔄 Re-run Stage", key=f"rerun_{stage}"):
                state[output_field] = ''
                st.session_state.interactive_state = state
                st.rerun()

        with col_restart:
            if st.button("🔙 Start Over", key=f"restart_{stage}"):
                st.session_state.interactive_stage = -1
                st.session_state.interactive_state = None
                st.rerun()

    # Pipeline complete
    elif current >= len(stages):
        st.success("✅ Interactive pipeline complete!")
        pipeline = st.session_state.interactive_pipeline
        result = pipeline.build_result(st.session_state.interactive_state)
        st.session_state.last_result = result
        st.session_state.total_spent += result['total_cost']

        if st.button("🔙 Reset Interactive Mode"):
            st.session_state.interactive_stage = -1
            st.session_state.interactive_state = None
            st.rerun()

# ==========================
# DISPLAY RESULTS
# ==========================
if st.session_state.last_result:
    result = st.session_state.last_result

    st.divider()
    st.subheader("📄 Your Content")

    # Tabs for different views
    tab_names = [
        "🎯 Final Output",
        "🔎 Fact-Check Report",
        "🔍 Research",
        "✍️ Draft",
        "📝 Edited",
        "💰 Cost Breakdown",
        "📊 Quality Score",
        "🛡️ Safety Report",
        "🔗 Pipeline Trace",
    ]
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(tab_names)

    with tab1:
        st.markdown("### Final Content (ready to publish)")
        st.markdown(result['final'])
        st.divider()
        st.download_button(
            label="📥 Download Content",
            data=result['final'],
            file_name=f"content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
        with st.expander("📋 Copy-paste version"):
            st.text_area("", value=result['final'], height=300, label_visibility="collapsed")

    with tab2:
        st.markdown("### Fact-Check Verification Report")
        report = result.get('fact_check_report', 'No report available')
        st.markdown(report)

    with tab3:
        st.markdown("### Research Notes")
        with st.expander("View Research Output", expanded=True):
            st.markdown(result['research'])

    with tab4:
        st.markdown("### Writer's Draft")
        with st.expander("View Draft", expanded=False):
            st.markdown(result['draft'])

    with tab5:
        st.markdown("### Editor's Version")
        with st.expander("View Edited Content", expanded=False):
            st.markdown(result['edited'])

    with tab6:
        st.markdown("### Cost Breakdown")
        metadata = result['metadata']
        col1, col2, col3, col4 = st.columns(4)

        for col, agent, key in [
            (col1, "Researcher", "researcher"),
            (col2, "Writer", "writer"),
            (col3, "Editor", "editor"),
            (col4, "Fact-Checker", "fact_checker"),
        ]:
            with col:
                tokens = metadata.get(f'{key}_tokens', {})
                total_tokens = tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)
                cached = metadata.get(f'{key}_cached', False)
                label = f"{agent} {'(cached)' if cached else ''}"
                st.metric(label, f"${metadata.get(f'{key}_cost', 0):.4f}",
                          delta=f"{total_tokens} tokens")

        st.divider()
        st.metric("Total Cost", f"${result['total_cost']:.4f}")

        # Cache stats
        cache_stats = result.get('cache_stats', {})
        if cache_stats.get('hits', 0) > 0 or cache_stats.get('misses', 0) > 0:
            st.caption(
                f"Cache: {cache_stats.get('hits', 0)} hits, "
                f"{cache_stats.get('misses', 0)} misses, "
                f"${cache_stats.get('cost_saved', 0):.4f} saved"
            )

    with tab7:
        st.markdown("### Quality Metrics")
        qs = result.get('quality_score', {})

        if qs:
            col_grade, col_words, col_overall = st.columns(3)
            with col_grade:
                st.metric("Overall Grade", qs.get('grade', 'N/A'))
            with col_words:
                st.metric("Word Count", qs.get('word_count', 0))
            with col_overall:
                st.metric("Overall Score", f"{qs.get('overall_score', 0):.0%}")

            st.divider()

            col_rel, col_faith, col_stats = st.columns(3)
            with col_rel:
                st.metric("Relevancy", f"{qs.get('relevancy_score', 0):.0%}",
                          help="LLM-judged: is the content on-topic?")
            with col_faith:
                st.metric("Faithfulness", f"{qs.get('faithfulness_score', 0):.0%}",
                          help="LLM-judged: does content match the research?")
            with col_stats:
                st.metric("Sentences", qs.get('sentence_count', 0))

            st.caption(
                f"Avg sentence length: {qs.get('avg_sentence_length', 0):.1f} words"
            )
        else:
            st.info("Quality scoring not available")

    with tab8:
        st.markdown("### Safety Report")
        gr = result.get('guardrail_report', {})

        if gr:
            # Input check
            input_gr = gr.get('input', {})
            risk = input_gr.get('risk_level', 'safe')
            if risk == 'safe':
                st.success("Input: SAFE - No issues detected")
            elif risk == 'warning':
                st.warning(f"Input: WARNING - {', '.join(input_gr.get('flags', []))}")
            elif risk == 'blocked':
                st.error(f"Input: BLOCKED - {', '.join(input_gr.get('flags', []))}")

            # PII in input
            pii_in = input_gr.get('pii_detected', [])
            if pii_in:
                st.warning(f"PII detected in input: {len(pii_in)} item(s)")
                for p in pii_in:
                    st.caption(f"  - {p['type']}: {p['value'][:20]}...")

            # Output check
            output_gr = gr.get('output', {})
            if output_gr:
                risk_out = output_gr.get('risk_level', 'safe')
                if risk_out == 'safe':
                    st.success("Output: SAFE - No PII leakage detected")
                else:
                    pii_out = output_gr.get('pii_detected', [])
                    st.warning(f"Output: PII detected and redacted ({len(pii_out)} items)")
        else:
            st.info("No guardrail report available (interactive mode)")

    with tab9:
        st.markdown("### Pipeline Trace")
        trace = result.get('trace', {})

        if trace:
            st.code(f"Trace ID: {trace.get('trace_id', 'N/A')}", language=None)

            col_dur, col_events, col_errors = st.columns(3)
            with col_dur:
                dur = trace.get('total_duration_ms', 0)
                st.metric("Duration", f"{dur / 1000:.1f}s")
            with col_events:
                st.metric("Events", trace.get('event_count', 0))
            with col_errors:
                st.metric("Errors", trace.get('error_count', 0))

            # Node timings
            st.markdown("#### Agent Timings")
            timings = trace.get('node_timings', {})
            if timings:
                for agent, ms in timings.items():
                    st.progress(min(ms / max(max(timings.values()), 1), 1.0),
                                text=f"{agent}: {ms / 1000:.1f}s")

            # Event timeline
            timeline = result.get('trace_timeline', [])
            if timeline:
                with st.expander("Event Timeline", expanded=False):
                    for event in timeline:
                        etype = event.get('event_type', '')
                        agent = event.get('agent', '')
                        ts = event.get('timestamp', '')[:19]
                        if etype == 'llm_call':
                            tokens = (event.get('input_tokens', 0) or 0) + (event.get('output_tokens', 0) or 0)
                            st.caption(f"[{ts}] {etype} | {agent} | {tokens} tokens | ${event.get('cost', 0):.4f}")
                        elif etype == 'error':
                            st.caption(f"[{ts}] {etype} | {agent} | {event.get('error', '')}")
                        else:
                            dur = event.get('duration_ms')
                            dur_str = f" | {dur:.0f}ms" if dur else ""
                            st.caption(f"[{ts}] {etype} | {agent}{dur_str}")
        else:
            st.info("No trace data available")

# How to use
with st.expander("💡 How to Use"):
    st.markdown("""
    **Create content in 3 steps:**

    1. **Enter your topic** - Be specific for better results
    2. **Pick format & tone** - Blog post, LinkedIn, or Twitter thread
    3. **Click Create** - Watch 4 AI agents collaborate

    **Modes:**
    - **Automatic** - Full pipeline runs end-to-end
    - **Interactive** - Review and edit each agent's output before continuing

    **Features:**
    - 🛡️ **Guardrails** - PII detection, prompt injection protection
    - 📊 **Quality Scoring** - Readability, relevancy, faithfulness metrics
    - 💾 **Caching** - Repeated topics reuse cached results (saves cost)
    - 🔗 **Tracing** - Full pipeline observability with timing data
    - 🔄 **Resilience** - Automatic retry on transient API failures
    """)

# Footer
st.divider()
st.caption(
    "Multi-Agent Content Pipeline | Powered by AWS Bedrock (Claude 3.5 Haiku) | "
    "Guardrails + Quality Scoring + Caching + Tracing + Human-in-the-Loop"
)
