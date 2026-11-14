import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = "openai/gpt-oss-20b"
# Alternative: "mixtral-8x7b-32768" — better reasoning, larger context


class LLMError(RuntimeError):
    """A sanitized Groq request failure safe to show in the application UI."""


_client = None


def _get_client():
    """Create the Groq client on demand so apps can start without API config."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise LLMError("GROQ_API_KEY is not configured. Add it to the project environment and retry.")
        _client = Groq(api_key=api_key)
    return _client

def chat(system_prompt: str, messages: list[dict], max_tokens: int = 1024) -> str:
    """
    Send a RAG-augmented chat request to Groq.
    messages = list of {"role": "user"/"assistant", "content": "..."}
    """
    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise LLMError("Groq returned an empty response. Please try again.")
        return content

    except Exception as e:
        err = str(e).lower()
        if "authentication" in err or "api key" in err:
            message = "Groq authentication failed. Check that GROQ_API_KEY is configured."
        elif "rate limit" in err:
            message = "Groq rate limit reached. Please wait briefly and retry."
        elif "connection" in err:
            message = "Could not connect to Groq. Check the network connection and retry."
        else:
            message = "The Groq request failed. Check the server logs and retry."
        if isinstance(e, LLMError):
            raise
        raise LLMError(message) from e
