import os
from langchain_openai import ChatOpenAI

def get_llm(temperature: float = 0.7, model: str = "qwen-max"):
    """
    Initializes the Qwen Cloud API client using the OpenAI compatible endpoint.
    Requires QWEN_API_KEY environment variable — never hardcode the key here.
    """
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "QWEN_API_KEY is not set. Add it to your .env file or export it as an "
            "environment variable. Never paste the key directly into source code."
        )
    # Qwen's OpenAI-compatible endpoint
    base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature
    )

def get_structured_llm(schema, temperature: float = 0.1, model: str = "qwen-max"):
    """Returns an LLM bound to a specific JSON schema for routing decisions."""
    llm = get_llm(temperature=temperature, model=model)
    return llm.with_structured_output(schema)
