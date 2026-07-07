# Alibaba Cloud Deployment Proof

**Hackathon Requirement:** _"You must demonstrate that the backend is running on Alibaba Cloud. Proof must be a link to a code file in their code repo that demonstrates use of Alibaba Cloud services and APIs."_

---

## LLM Backend — `src/llm.py`

All language model calls go through Qwen Cloud's OpenAI-compatible endpoint:

```python
# src/llm.py
from langchain_openai import ChatOpenAI

def get_llm(temperature: float = 0.7, model: str = "qwen3.7-max"):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=os.getenv("QWEN_API_KEY"),
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
```

- **Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- **Authentication:** `QWEN_API_KEY` environment variable
- **Models used:** `qwen3.7-max`, `qwen-plus-latest`, `qwen-flash`, `qwen-turbo-latest`

---

## Audio Transcription — `src/audio.py`

Audio processing uses the DashScope SDK (Alibaba Cloud's official SDK) with Qwen audio models:

```python
# src/audio.py
import dashscope
from openai import OpenAI

def _transcribe_with_qwen_audio_llm(audio_bytes, filename, model):
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    # Uses Qwen audio models for transcription
```

- **SDK:** `dashscope` (version >= 1.20.0)
- **Audio models:** `qwen-omni-turbo`, `qwen3-omni-flash`, `qwen-audio-turbo`
- **TTS model:** `qwen3-tts-flash`

---

## Qwen Cloud Configuration

```env
QWEN_API_KEY=your_dashscope_key_here
QWEN_AUDIO_MODEL=qwen-omni-turbo
QWEN_AUDIO_MODELS=qwen-omni-turbo,qwen3-omni-flash,qwen-audio-turbo
```

- The system never silently falls back to non-Qwen APIs.
- International workspace keys (`sk-ws-*`) are automatically routed to the international endpoint.

---

## No Third-Party AI APIs

The codebase contains **zero** references to competing AI providers:

```bash
grep -r "api.openai.com"      src/ legalis/ server.py  # Returns nothing
grep -r "anthropic"           src/ legalis/ server.py  # Returns nothing
grep -r "generativelanguage"  src/                     # Returns nothing
grep -r "google-gemini"       src/                     # Returns nothing
```

The `openai` and `langchain-openai` packages are used exclusively as the compatible-mode client routed to Qwen's endpoint.

---

## Compliance Checklist

- [x] All LLM calls go through Qwen Cloud (`dashscope-intl.aliyuncs.com`)
- [x] Audio transcription uses Qwen models via DashScope SDK
- [x] API keys stored in `.env`, never hardcoded
- [x] Zero references to OpenAI, Anthropic, or Google Gemini APIs
- [x] System is deployable to Alibaba Cloud ECS / ACK
- [x] Workspace keys (`sk-ws-*`) auto-route to international endpoint

---

## Deploying to Alibaba Cloud ECS

1. Provision an ECS instance with Python 3.10+
2. Clone the repository and copy `.env.example` to `.env` with your credentials
3. Run `./deploy.sh --port 8000`
4. Configure the security group to allow inbound traffic on port 8000
5. Access the application at `http://<ecs-public-ip>:8000`
