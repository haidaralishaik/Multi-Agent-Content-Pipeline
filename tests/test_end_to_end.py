"""End-to-end pipeline testing"""
from dotenv import load_dotenv
load_dotenv()

from src.pipeline import ContentPipeline
from pathlib import Path
import json


def test_various_topics():
    """Test pipeline with different topic types"""
    pipeline = ContentPipeline()

    topics = [
        # Technical topic
        ("RAG systems overview", 500),

        # Recent events (tests web search capability)
        ("Latest AI developments in 2024", 400),

        # How-to topic
        ("How to build a multi-agent system", 600),
    ]

    for topic, expected_min_length in topics:
        print(f"\n{'='*60}")
        print(f"Testing: {topic}")
        print(f"{'='*60}")

        result = pipeline.run(topic)

        # Verify all stages completed
        assert len(result['research']) > 0
        assert len(result['draft']) > 0
        assert len(result['edited']) > 0
        assert len(result['final']) > 0

        # Verify final output has substance
        assert len(result['final']) > expected_min_length

        # Verify reasonable cost
        assert result['total_cost'] < 0.10, "Cost too high!"

        print(f"[OK] Passed: {len(result['final'])} chars, ${result['total_cost']:.4f}")


def test_error_handling():
    """Test pipeline handles errors gracefully"""
    pipeline = ContentPipeline()

    # Very vague topic (might be challenging)
    result = pipeline.run("stuff")

    # Should complete even with vague topic
    assert result is not None

    # Check if errors were logged
    if result['errors']:
        print(f"Errors encountered (expected): {result['errors']}")

    print("[OK] Error handling works")


def test_output_saving():
    """Test outputs are saved properly"""
    pipeline = ContentPipeline()

    result = pipeline.run("Test topic for file saving")

    # Save output
    output_file = Path('outputs/test_output.json')
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    # Verify file exists
    assert output_file.exists()

    # Verify can load back
    with open(output_file, 'r') as f:
        loaded = json.load(f)

    assert loaded['topic'] == result['topic']

    print(f"[OK] Output saved to: {output_file}")


if __name__ == "__main__":
    print("Running comprehensive tests...")
    print("This will take 5-10 minutes and cost ~$0.30")

    input("Press Enter to continue...")

    test_various_topics()
    print("\n" + "="*60)
    test_error_handling()
    print("\n" + "="*60)
    test_output_saving()

    print("\n[DONE] All end-to-end tests passed!")
