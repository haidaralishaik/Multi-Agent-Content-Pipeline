"""
Groq LLM Client

Uses Groq (free tier, 6000 req/day) — LLaMA 3.3 70B.
"""

import os
import json
from typing import Callable, Dict, List, Optional
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

    def invoke_with_tools(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_executors: Optional[Dict[str, Callable]] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        max_tool_rounds: int = 6,
    ) -> Dict:
        """
        Invoke with Groq tool calling. Runs the agentic loop until the LLM
        produces a final response with no tool calls.

        Args:
            messages:       Conversation messages
            system:         System prompt
            tools:          Groq-format tool definitions
            tool_executors: {tool_name: callable(**args) -> str}
            max_tool_rounds: Safety cap on tool call iterations

        Returns:
            Same shape as invoke(): {content, usage, stop_reason}
        """
        groq_messages: List[Dict] = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        total_input = 0
        total_output = 0

        for _ in range(max_tool_rounds):
            call_kwargs: Dict = dict(
                model=self.model_id,
                messages=groq_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if tools:
                call_kwargs["tools"] = tools
                call_kwargs["tool_choice"] = "auto"

            response = self._retry_handler.execute_with_retry(
                self._client.chat.completions.create, **call_kwargs
            )
            total_input += response.usage.prompt_tokens if response.usage else 0
            total_output += response.usage.completion_tokens if response.usage else 0

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                # Final answer — no more tool calls
                return {
                    "content": msg.content or "",
                    "usage": {"input_tokens": total_input, "output_tokens": total_output},
                    "stop_reason": choice.finish_reason or "end_turn",
                }

            # Append assistant message (with tool_calls)
            groq_messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # Execute each tool and append results
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                if tool_executors and tool_name in tool_executors:
                    try:
                        result_str = str(tool_executors[tool_name](**tool_args))
                    except Exception as exc:
                        result_str = f"Tool error: {exc}"
                else:
                    result_str = f"Unknown tool: {tool_name}"

                logger.info(f"Tool called: {tool_name}({tool_args})")
                groq_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        # Fallback if max rounds reached
        last_content = next(
            (m.get("content", "") for m in reversed(groq_messages) if m.get("role") == "assistant"),
            "",
        )
        return {
            "content": last_content,
            "usage": {"input_tokens": total_input, "output_tokens": total_output},
            "stop_reason": "max_tool_rounds",
        }

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
