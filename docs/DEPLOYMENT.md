# Alibaba Cloud Deployment Proof

**Hackathon Requirement:** _"You must demonstrate that the backend is running on Alibaba Cloud. Proof must be a link to a code file in their code repo that demonstrates use of Alibaba Cloud services and APIs."_

---

## LLM Backend — `src/llm.py`

All language model calls go through Qwen Cloud's OpenAI-compatible endpoint:

```python
# src/llm.py
from langchain_openai import ChatOpenAI

def get_llm(temperature: float = 0.7, model: str = "qwen-max"):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=os.getenv("QWEN_API_KEY"),
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
```

- **Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- **Authentication:** `QWEN_API_KEY` environment variable
- **Models used:** `qwen-max`, `qwen-plus-latest`, `qwen-flash`, `qwen-turbo-latest`

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

## Live Deployment on Alibaba Cloud ECS

Codex Legalis is currently deployed and running live on an Alibaba Cloud ECS instance.

- **Live URL:** [http://47.237.180.168:8000](http://47.237.180.168:8000)
- **Deployment Method:** Docker container running on Ubuntu 24.04 (Alibaba ECS)
- **Instance IP:** `47.237.180.168`

To update the live deployment after pushing new code, we use our automated Docker deployment script on the server:
```bash
./deploy-docker.sh
```
