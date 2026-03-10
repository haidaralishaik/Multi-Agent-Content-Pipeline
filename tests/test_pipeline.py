"""Test multi-agent pipeline"""
from dotenv import load_dotenv
load_dotenv()

from src.pipeline import ContentPipeline
import time


def test_pipeline_creation():
    """Test creating pipeline"""
    pipeline = ContentPipeline()

    assert pipeline.researcher is not None
    assert pipeline.writer is not None
    assert pipeline.editor is not None
    assert pipeline.fact_checker is not None

    print("[OK] Pipeline created with all 4 agents")


def test_simple_pipeline_run():
    """Test running pipeline with simple topic"""
    pipeline = ContentPipeline()

    print("\nRunning pipeline...")
    print("This will take 1-2 minutes (4 agents x ~15-20 seconds each)")

    start_time = time.time()

    result = pipeline.run(
        topic="What is RAG and why is it useful? (Keep brief, under 300 words total)"
    )

    duration = time.time() - start_time

    print(f"\n{'='*60}")
    print("PIPELINE RESULTS")
    print(f"{'='*60}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Total Cost: ${result['total_cost']:.4f}")
    print(f"Errors: {len(result['errors'])}")

    if result['errors']:
        print(f"\nErrors encountered:")
        for error in result['errors']:
            print(f"  - {error}")

    # Check all stages completed
    assert len(result['research']) > 0, "Research output empty"
    assert len(result['draft']) > 0, "Draft output empty"
    assert len(result['edited']) > 0, "Edited output empty"
    assert len(result['final']) > 0, "Final output empty"

    print("\nOutput Sizes:")
    print(f"  Research: {len(result['research'])} chars")
    print(f"  Draft: {len(result['draft'])} chars")
    print(f"  Edited: {len(result['edited'])} chars")
    print(f"  Final: {len(result['final'])} chars")

    print(f"\n{'='*60}")
    print("FINAL FACT-CHECK REPORT")
    print(f"{'='*60}")
    print(result['final'][:500] + "...")

    print("\n[OK] Pipeline test passed!")


if __name__ == "__main__":
    test_pipeline_creation()
    print("\n" + "="*60)
    test_simple_pipeline_run()
    print("\n[DONE] Pipeline tests complete!")
