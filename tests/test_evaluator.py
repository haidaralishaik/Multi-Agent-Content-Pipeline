"""Tests for content evaluator"""

from src.evaluator import ContentEvaluator


def test_text_stats_simple():
    """Text stats work on simple text"""
    e = ContentEvaluator()
    simple = "The cat sat on the mat. The dog ran in the park. It was a nice day."
    result = e.compute_text_stats(simple)
    assert result['word_count'] > 0
    assert result['sentence_count'] == 3
    assert result['avg_sentence_length'] > 0


def test_text_stats_empty():
    """Empty text handled gracefully"""
    e = ContentEvaluator()
    result = e.compute_text_stats("")
    assert result['word_count'] == 0


def test_text_stats_markdown():
    """Markdown is stripped before counting"""
    e = ContentEvaluator()
    md = "# Heading\n\n**Bold text** and [a link](https://example.com). Normal sentence."
    result = e.compute_text_stats(md)
    assert result['word_count'] > 0
    assert result['sentence_count'] >= 2


def test_evaluate_without_llm():
    """Evaluate works without Bedrock client"""
    e = ContentEvaluator(bedrock_client=None)
    text = "AI systems are transforming how we work. They help with many tasks. The future looks bright."
    score = e.evaluate(text)
    assert score.word_count > 0
    assert score.grade in ("A", "B", "C", "D", "F")
    assert score.overall_score > 0


def test_score_to_grade():
    """Grade assignment is correct"""
    assert ContentEvaluator._score_to_grade(0.90) == "A"
    assert ContentEvaluator._score_to_grade(0.75) == "B"
    assert ContentEvaluator._score_to_grade(0.60) == "C"
    assert ContentEvaluator._score_to_grade(0.45) == "D"
    assert ContentEvaluator._score_to_grade(0.30) == "F"


def test_quality_score_to_dict():
    """QualityScore serializes to dict"""
    e = ContentEvaluator()
    score = e.evaluate("Simple test text. Another sentence here.")
    d = score.to_dict()
    assert isinstance(d, dict)
    assert 'grade' in d
    assert 'word_count' in d
    assert 'relevancy_score' in d
    assert 'faithfulness_score' in d
