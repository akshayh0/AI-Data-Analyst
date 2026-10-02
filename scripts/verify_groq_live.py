import os
from dotenv import load_dotenv
from app.config import settings
from app.llm.groq_provider import GroqProvider

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

print(f"GROQ_API_KEY present: {bool(api_key and len(api_key) > 10)}")
print(f"GROQ_MODEL: {model}")
print(f"Fallback MODEL: {settings.groq_fallback_model}")

provider = GroqProvider()
print(f"Provider class: {type(provider).__name__}")
assert type(provider).__name__ == "GroqProvider", "Must be GroqProvider"

from app.llm.base import LLMMessage
resp = provider.generate([LLMMessage(role="user", content="Answer with only the word OK: Are you connected?")], temperature=0.0)
print(f"Groq live response: {resp.content.strip()}")
print("Groq verification: PASS")
