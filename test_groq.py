"""
Test Groq API connection
"""
from dotenv import load_dotenv
load_dotenv()

from src.groq_client import GroqClient

try:
    client = GroqClient()

    response = client.invoke_with_system(
        user_message="Say 'Hello from Groq!' and nothing else.",
        system_prompt="You are a helpful assistant.",
        max_tokens=50,
    )

    print("[OK] Groq is working!")
    print(f"Response: {response}")

except Exception as e:
    print(f"[ERROR] {e}")
    print("\nTroubleshooting:")
    print("1. Check GROQ_API_KEY is set in your .env file")
    print("2. Get a free key at https://console.groq.com/keys")
