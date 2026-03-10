"""Test agent core with Bedrock"""
from dotenv import load_dotenv
load_dotenv()

from src.agent_core import InstructionBasedAgent
import time


def test_agent_creation():
    """Test creating agents"""
    roles = ['researcher', 'writer', 'editor', 'fact_checker']

    for role in roles:
        agent = InstructionBasedAgent(role=role)
        assert agent.role == role
        assert agent.instructions is not None
        assert len(agent.instructions) > 0
        print(f"[OK] Created {role} agent: {len(agent.instructions)} char instructions")


def test_simple_execution():
    """Test agent executing a simple task"""
    agent = InstructionBasedAgent(role='researcher')

    result = agent.execute(
        task="What is RAG? (Keep answer under 50 words)",
        max_tokens=200
    )

    assert result['output'] is not None
    assert len(result['output']) > 0
    assert result['cost'] > 0
    assert result['role'] == 'researcher'

    print(f"\n[OK] Agent execution successful!")
    print(f"Output length: {len(result['output'])} chars")
    print(f"Cost: ${result['cost']:.6f}")
    print(f"Tokens: {result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out")
    print(f"\nOutput:\n{result['output']}")


def test_agent_with_context():
    """Test agent using context from previous agent"""
    researcher = InstructionBasedAgent(role='researcher')

    # Researcher does research
    research_result = researcher.execute(
        task="Research: Key benefits of RAG (keep brief)",
        max_tokens=500
    )

    print(f"\n{'='*60}")
    print(f"RESEARCHER OUTPUT")
    print(f"{'='*60}")
    print(research_result['output'][:200] + "...")

    # Writer uses researcher's output as context
    writer = InstructionBasedAgent(role='writer')

    writer_result = writer.execute(
        task="Write a 2-paragraph blog intro about RAG benefits",
        context={
            "Research Notes": research_result['output']
        },
        max_tokens=500
    )

    print(f"\n{'='*60}")
    print(f"WRITER OUTPUT")
    print(f"{'='*60}")
    print(writer_result['output'])

    total_cost = research_result['cost'] + writer_result['cost']
    print(f"\n{'='*60}")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"[OK] Multi-agent pipeline works!")


if __name__ == "__main__":
    print("Testing agent creation...")
    test_agent_creation()

    print("\n" + "="*60)
    print("Testing simple execution...")
    test_simple_execution()

    print("\n" + "="*60)
    print("Testing agent with context...")
    test_agent_with_context()

    print("\n[DONE] All agent tests passed!")
