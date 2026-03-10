"""
Content Evaluator - Quality scoring for pipeline outputs

Provides:
- Word count and sentence statistics
- LLM-as-judge scoring (relevancy, faithfulness) via Bedrock
- Composite quality grades (A-F)
"""

import re
import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality evaluation result for a piece of content"""
    word_count: int = 0
    sentence_count: int = 0
    avg_sentence_length: float = 0.0
    relevancy_score: float = 0.0         # 0-1, LLM-judged
    faithfulness_score: float = 0.0      # 0-1, LLM-judged
    overall_score: float = 0.0           # Weighted composite
    grade: str = ""                      # A/B/C/D/F
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


class ContentEvaluator:
    """
    Evaluates content quality using LLM-as-judge metrics.

    Scores relevancy (is the content on-topic?) and faithfulness
    (does the content match the research?) using the same Bedrock
    model that powers the pipeline agents.
    """

    def __init__(self, bedrock_client=None):
        self.bedrock = bedrock_client

    # --- Text Statistics ---

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Strip markdown formatting for plain-text analysis."""
        cleaned = text
        cleaned = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', cleaned)
        cleaned = re.sub(r'https?://\S+', '', cleaned)
        cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', cleaned)
        cleaned = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', cleaned)
        cleaned = re.sub(r'^\s*[-*+]\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*\d+\.\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'```[^`]*```', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'`([^`]*)`', r'\1', cleaned)
        cleaned = re.sub(r'^---+\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^>\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'[\u2014\u2013]', ' ', cleaned)
        cleaned = re.sub(r'(\w)-(\w)', r'\1 \2', cleaned)
        return cleaned

    def compute_text_stats(self, text: str) -> Dict:
        """Compute word count, sentence count, and avg sentence length."""
        if not text or not text.strip():
            return {"word_count": 0, "sentence_count": 0, "avg_sentence_length": 0}

        clean = self._strip_markdown(text)
        clean = re.sub(r'\n{2,}', '. ', clean)
        clean = re.sub(r'\n', ' ', clean)

        sentences = [s.strip() for s in re.split(r'[.!?]+', clean) if s.strip()]
        words = [w for w in clean.split() if w.strip()]

        sentence_count = max(len(sentences), 1)
        word_count = len(words)
        avg_sentence_length = round(word_count / sentence_count, 1) if sentence_count else 0

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": avg_sentence_length,
        }

    # --- LLM-as-Judge Metrics ---

    def evaluate_relevancy(self, content: str, topic: str) -> float:
        """LLM-as-judge: how relevant is the content to the topic? Returns 0.0-1.0."""
        if not self.bedrock:
            return 0.0

        prompt = (
            "You are a content evaluator. Rate how relevant the following content "
            "is to the given topic on a scale of 0.0 to 1.0.\n\n"
            f"TOPIC: {topic}\n\n"
            f"CONTENT (first 1500 chars): {content[:1500]}\n\n"
            "Respond with ONLY a JSON object: {\"score\": 0.X, \"reason\": \"brief explanation\"}"
        )

        try:
            result = self.bedrock.invoke(
                messages=[{"role": "user", "content": prompt}],
                system="You are a precise content evaluator. Return only valid JSON.",
                max_tokens=200,
                temperature=0.0,
            )
            parsed = json.loads(result['content'])
            return float(parsed.get('score', 0.0))
        except (json.JSONDecodeError, KeyError, ValueError, Exception) as e:
            logger.warning(f"Relevancy evaluation failed: {e}")
            return 0.0

    def evaluate_faithfulness(self, content: str, research: str) -> float:
        """LLM-as-judge: does the content faithfully represent the research? Returns 0.0-1.0."""
        if not self.bedrock:
            return 0.0

        prompt = (
            "You are a fact-checking evaluator. Rate how faithfully the content "
            "represents the research notes on a scale of 0.0 to 1.0.\n"
            "1.0 = all claims are supported by the research\n"
            "0.0 = content is entirely fabricated\n\n"
            f"RESEARCH NOTES (first 1500 chars): {research[:1500]}\n\n"
            f"CONTENT (first 1500 chars): {content[:1500]}\n\n"
            "Respond with ONLY a JSON object: {\"score\": 0.X, \"reason\": \"brief explanation\"}"
        )

        try:
            result = self.bedrock.invoke(
                messages=[{"role": "user", "content": prompt}],
                system="You are a precise content evaluator. Return only valid JSON.",
                max_tokens=200,
                temperature=0.0,
            )
            parsed = json.loads(result['content'])
            return float(parsed.get('score', 0.0))
        except (json.JSONDecodeError, KeyError, ValueError, Exception) as e:
            logger.warning(f"Faithfulness evaluation failed: {e}")
            return 0.0

    # --- Composite Scoring ---

    def evaluate(self, content: str, topic: str = "",
                 research: str = "") -> QualityScore:
        """
        Full evaluation of content quality.

        Uses LLM-as-judge for relevancy and faithfulness scoring.
        Falls back to text stats only when no Bedrock client is available.
        """
        stats = self.compute_text_stats(content)

        relevancy = self.evaluate_relevancy(content, topic) if topic else 0.0
        faithfulness = self.evaluate_faithfulness(content, research) if research else 0.0

        # Composite score from LLM judgments
        if topic and research and self.bedrock:
            overall = relevancy * 0.50 + faithfulness * 0.50
        elif self.bedrock and topic:
            overall = relevancy
        else:
            # No LLM available - use word count as a basic quality proxy
            # (at least 200 words for a blog post = 1.0)
            overall = min(stats['word_count'] / 200, 1.0) * 0.7

        grade = self._score_to_grade(overall)

        return QualityScore(
            word_count=stats['word_count'],
            sentence_count=stats['sentence_count'],
            avg_sentence_length=stats['avg_sentence_length'],
            relevancy_score=round(relevancy, 2),
            faithfulness_score=round(faithfulness, 2),
            overall_score=round(overall, 2),
            grade=grade,
            details=stats,
        )

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """Convert 0-1 score to letter grade."""
        if score >= 0.85:
            return "A"
        elif score >= 0.70:
            return "B"
        elif score >= 0.55:
            return "C"
        elif score >= 0.40:
            return "D"
        else:
            return "F"
