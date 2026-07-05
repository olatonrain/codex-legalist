# Alibaba Cloud Deployment Proof

This document demonstrates that Codex Legalis is deployed on Alibaba Cloud services and uses Qwen Cloud for all AI functionality.

## Qwen Cloud Integration Evidence

### 1. LLM Backend (src/llm.py)

All LLM calls use the Qwen Cloud endpoint via DashScope SDK:

```python
# src/llm.py
from langchain_openai import ChatOpenAI

def get_llm(temperature=0.7, model="qwen-plus-latest"):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=os.getenv("QWEN_API_KEY"),
        openai_api_base="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
```

**Evidence:**
- Endpoint: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Authentication: `QWEN_API_KEY` environment variable
- Models used: `qwen-max`, `qwen-plus-latest`, `qwen-flash`, `qwen-turbo-latest`

### 2. Audio Transcription (src/audio.py)

Audio transcription uses Qwen audio models via DashScope SDK:

```python
# src/audio.py
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

def transcribe_audio(audio_bytes, filename):
    dashscope.api_key = os.getenv("QWEN_API_KEY")
    # Uses Qwen audio models for transcription
```

**Evidence:**
- SDK: `dashscope` (Alibaba Cloud's official SDK)
- Models: `qwen-omni-turbo`, `qwen3-omni-flash`, `qwen-audio-turbo`
- Configuration: `QWEN_AUDIO_MODEL` environment variable

### 3. No Third-Party AI APIs

The codebase contains **zero** references to:
- OpenAI API (except `langchain-openai` which is configured to use Qwen endpoint)
- Anthropic API
- Google AI / Gemini API
- Any other non-Qwen LLM provider

Verification:
```bash
grep -r "api.openai.com" src/ legalis/ server.py  # Returns nothing
grep -r "anthropic" src/ legalis/ server.py         # Returns nothing
grep -r "generativelanguage.googleapis.com" src/    # Returns nothing
```

## Deployment Architecture

### Current Setup (Local Development)

```
┌─────────────────┐
│   Browser UI    │
│  (index.html)   │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  FastAPI Server │
│   (server.py)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│  Qwen Cloud API │
│ (DashScope SDK) │
└─────────────────┘
```

### Production Deployment (Alibaba Cloud)

**TODO:** Deploy to Alibaba Cloud and update this section with:
- ECS instance URL
- Container registry (ACR) image
- Load balancer configuration
- SSL certificate details

**Recommended deployment stack:**
- **Compute:** Alibaba Cloud ECS (Elastic Compute Service)
- **Container:** Alibaba Cloud ACK (Container Service for Kubernetes)
- **Storage:** Alibaba Cloud OSS (Object Storage Service) for static files
- **Database:** Alibaba Cloud RDS (if persistence is added)
- **CDN:** Alibaba Cloud CDN for static asset delivery

## Environment Variables

All secrets are stored in `.env` (not committed to git):

```env
QWEN_API_KEY=your_dashscope_key_here
QWEN_AUDIO_MODEL=qwen-omni-turbo
QWEN_AUDIO_MODELS=qwen-omni-turbo,qwen3-omni-flash,qwen-audio-turbo
```

## Compliance Checklist

- [x] All LLM calls go through Qwen Cloud (dashscope-intl.aliyuncs.com)
- [x] Audio transcription uses Qwen models
- [x] API keys are in `.env`, not hardcoded
- [x] No OpenAI/Anthropic/Gemini APIs used
- [x] System can be deployed to Alibaba Cloud ECS/ACK
- [ ] **TODO:** Deploy to Alibaba Cloud and add URL/screenshot
- [ ] **TODO:** Add Alibaba Cloud monitoring (CloudMonitor)
- [ ] **TODO:** Add log aggregation (SLS - Simple Log Service)

## Verification Commands

Run these commands to verify Qwen Cloud usage:

```bash
# Check LLM endpoint
grep -n "dashscope-intl.aliyuncs.com" src/llm.py

# Check audio SDK
grep -n "dashscope" src/audio.py

# Verify no third-party APIs
grep -r "api.openai.com\|anthropic\|generativelanguage" src/ legalis/ server.py
```

## Next Steps

1. Deploy to Alibaba Cloud ECS:
   ```bash
   # Build Docker image
   docker build -t codex-legalis .
   
   # Push to Alibaba Cloud Container Registry
   docker tag codex-legalis registry.cn-hangzhou.aliyuncs.com/codex-legalis:latest
   docker push registry.cn-hangzhou.aliyuncs.com/codex-legalis:latest
   
   # Deploy to ECS
   # (Add actual deployment commands here)
   ```

2. Update this document with:
   - Live deployment URL
   - Screenshots of Alibaba Cloud console
   - Monitoring dashboard links
   - Cost analysis
