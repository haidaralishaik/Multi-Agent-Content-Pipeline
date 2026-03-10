"""Tests for interactive (human-in-the-loop) pipeline"""

from src.pipeline_interactive import InteractivePipeline


def test_create_initial_state():
    """Initial state has all required fields"""
    pipeline = InteractivePipeline()
    state = pipeline.create_initial_state(
        topic="Test topic",
        content_format="blog_post",
        tone="professional",
    )
    assert state['topic'] == "Test topic"
    assert state['content_format'] == "blog_post"
    assert state['research_output'] == ''
    assert state['errors'] == []
    assert state['_tracer'] is not None


def test_inject_human_edit():
    """Human edits are properly injected into state"""
    pipeline = InteractivePipeline()
    state = pipeline.create_initial_state(topic="Test")

    state['research_output'] = "Original research"
    state = pipeline.inject_human_edit(
        state, "research",
        edited_content="Human-edited research",
        feedback="Added more sources",
    )

    assert state['research_output'] == "Human-edited research"
    assert state['metadata']['research_human_edited'] is True
    assert state['metadata']['research_human_feedback'] == "Added more sources"


def test_get_stage_output():
    """Can retrieve stage outputs by name"""
    pipeline = InteractivePipeline()
    state = pipeline.create_initial_state(topic="Test")
    state['research_output'] = "Research text"
    state['draft_output'] = "Draft text"

    assert pipeline.get_stage_output(state, "research") == "Research text"
    assert pipeline.get_stage_output(state, "write") == "Draft text"


def test_stages_list():
    """Stages list is correct"""
    assert InteractivePipeline.STAGES == ["research", "write", "edit", "fact_check"]


def test_invalid_stage_raises():
    """Invalid stage name raises ValueError"""
    pipeline = InteractivePipeline()
    state = pipeline.create_initial_state(topic="Test")

    try:
        pipeline.run_stage("invalid", state)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    try:
        pipeline.inject_human_edit(state, "invalid", "text")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
