"""
Groq LLM Client

Uses Groq (free tier, 6000 req/day) — LLaMA 3.3 70B.
"""

import os
from typing import Dict, List, Optional
import logging

from src.resilience import RetryHandler, RetryConfig

logger = logging.getLogger(__name__)


class GroqClient:
    """LLM client powered by Groq (free tier, 6000 req/day, LLaMA 3.3 70B)."""

    def __init__(
        self,
        region_name: str = None,   # kept for interface compatibility, unused
        model_id: str = None
    ):
        from groq import Groq

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. "
                "Get a free key at https://console.groq.com/keys"
            )

        self._client = Groq(api_key=api_key)
        self.model_id = model_id or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

        logger.info(f"Groq client initialized: {self.model_id}")

        self._retry_handler = RetryHandler(RetryConfig(
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
        ))

    def invoke(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> Dict:
        """
        Invoke Groq model.

        Args:
            messages: List of messages with 'role' and 'content' keys
            system: System prompt (instructions)
            max_tokens: Max tokens to generate
            temperature: Creativity (0-1)

        Returns:
            {
                'content': str,
                'usage': {'input_tokens': int, 'output_tokens': int},
                'stop_reason': str
            }
        """
        # Prepend system message if provided
        groq_messages = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        try:
            response = self._retry_handler.execute_with_retry(
                self._client.chat.completions.create,
                model=self.model_id,
                messages=groq_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            result = {
                'content': content,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                },
                'stop_reason': response.choices[0].finish_reason or 'end_turn',
            }

            if self._retry_handler.retry_history:
                result['retries'] = list(self._retry_handler.retry_history)
                self._retry_handler.retry_history.clear()

            return result

        except Exception as e:
            logger.error(f"Groq invocation failed: {e}")
            raise

    def invoke_with_system(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int = 4000
    ) -> str:
        """
        Simple helper: invoke with system prompt and single user message.

        Returns:
            Response text
        """
        messages = [{"role": "user", "content": user_message}]
        result = self.invoke(
            messages=messages,
            system=system_prompt,
            max_tokens=max_tokens
        )
        return result['content']


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    client = GroqClient()

    response = client.invoke_with_system(
        user_message="Say 'Groq client is working!' and nothing else.",
        system_prompt="You are a helpful assistant."
    )

    print(f"[OK] Response: {response}")
