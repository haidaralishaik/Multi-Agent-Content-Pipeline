"""
Agent Core - Instruction-based agent powered by AWS Bedrock

This is where instruction files meet AWS Bedrock!
"""

from src.instruction_loader import InstructionLoader
from src.bedrock_client import BedrockClient
from src.cost_tracker import BedrockCostTracker
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class InstructionBasedAgent:
    """
    Agent that reads instruction files and uses AWS Bedrock

    This is the core innovation:
    - Behavior comes from .md files (not code!)
    - Powered by AWS Bedrock
    - Tracks costs automatically
    """

    def __init__(
        self,
        role: str,
        tools: Optional[List] = None,
        instructions_dir: str = 'instructions'
    ):
        """
        Initialize agent

        Args:
            role: Agent role (researcher, writer, editor, fact_checker)
            tools: List of tools available to agent (optional)
            instructions_dir: Where instruction files live
        """
        self.role = role
        self.tools = tools or []

        # Load instructions
        self.loader = InstructionLoader(instructions_dir)
        self.instructions = self.loader.get_full_instructions(role)

        # Initialize Bedrock
        self.bedrock = BedrockClient()

        # Initialize cost tracking
        self.tracker = BedrockCostTracker()

        logger.info(f"Agent initialized: {role} with {len(self.instructions)} char instructions")

    def execute(
        self,
        task: str,
        context: Optional[Dict] = None,
        max_tokens: int = 4000
    ) -> Dict:
        """
        Execute task using instructions

        Args:
            task: What to do (e.g., "Research: Recent RAG advances")
            context: Additional context (previous agent outputs, etc.)
            max_tokens: Max response length

        Returns:
            {
                'output': str (agent's response),
                'usage': dict (tokens used),
                'cost': float,
                'role': str (which agent)
            }
        """
        # Build user message
        user_message = self._build_user_message(task, context)

        logger.info(f"{self.role.upper()} executing task: {task[:100]}...")

        try:
            # Call Bedrock with instructions as system prompt
            result = self.bedrock.invoke(
                messages=[
                    {"role": "user", "content": user_message}
                ],
                system=self.instructions,  # Instructions become system prompt!
                max_tokens=max_tokens
            )

            # Track cost
            cost = self.tracker.track_call(
                agent_name=self.role,
                input_tokens=result['usage']['input_tokens'],
                output_tokens=result['usage']['output_tokens'],
                description=f"Task: {task[:50]}"
            )

            logger.info(
                f"{self.role.upper()} completed: "
                f"{result['usage']['output_tokens']} tokens, "
                f"${cost:.6f}"
            )

            return {
                'output': result['content'],
                'usage': result['usage'],
                'cost': cost,
                'role': self.role,
                'stop_reason': result['stop_reason']
            }

        except Exception as e:
            logger.error(f"{self.role.upper()} failed: {e}")
            raise

    def _build_user_message(self, task: str, context: Optional[Dict]) -> str:
        """
        Build the actual user message from task + context

        Args:
            task: The task description
            context: Previous agent outputs

        Returns:
            Formatted user message
        """
        message_parts = []

        # Add context if provided
        if context:
            message_parts.append("## CONTEXT FROM PREVIOUS AGENTS")

            for key, value in context.items():
                message_parts.append(f"\n### {key}")
                message_parts.append(str(value))

            message_parts.append("\n---\n")

        # Add the task
        message_parts.append("## YOUR TASK")
        message_parts.append(task)

        return "\n".join(message_parts)

    def reload_instructions(self):
        """
        Reload instructions from files

        Useful during development when editing instruction files
        """
        self.loader.reload_instructions()
        self.instructions = self.loader.get_full_instructions(self.role)
        logger.info(f"{self.role.upper()} instructions reloaded")


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Create a researcher agent
    researcher = InstructionBasedAgent(role='researcher')

    # Give it a task
    result = researcher.execute(
        task="Research: What are recent advances in RAG systems?"
    )

    print(f"\n{'='*60}")
    print(f"RESEARCHER OUTPUT")
    print(f"{'='*60}")
    print(result['output'])
    print(f"\n{'='*60}")
    print(f"Cost: ${result['cost']:.6f}")
    print(f"Tokens: {result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out")
