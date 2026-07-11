# Deployment Guide

## Prerequisites

- Python 3.11+
- Qwen Cloud API key (`QWEN_API_KEY` in `.env`)
- Git

## Quick Deploy (Local)

```bash
git clone https://github.com/olatonrain/codex-legalist.git
cd codex-legalist

cp .env.example .env
# Edit .env and add your QWEN_API_KEY

./deploy.sh
```

The `deploy.sh` script:
1. Creates a Python virtual environment (`venv/`) if missing
2. Installs dependencies from `requirements.txt`
3. Copies `.env.example` to `.env` if `.env` is missing
4. Kills any process on the target port
5. Starts `uvicorn server:app --host 0.0.0.0 --port 8000`

Open [http://localhost:8000](http://localhost:8000).

## Docker Deploy

```bash
./deploy-docker.sh
```

The `deploy-docker.sh` script:
1. `git fetch --all && git reset --hard origin/main`
2. `docker build --no-cache -t codex-legalist .`
3. `docker rm -f legalist_app || true`
4. `docker run -d --name legalist_app -p 8000:8000 --restart unless-stopped codex-legalist`

## Manual Deploy (VPS / Alibaba Cloud ECS)

```bash
# SSH into your VPS
ssh ubuntu@<instance-ip>

# Clone/pull the repo
git clone https://github.com/olatonrain/codex-legalist.git
cd codex-legalist

# Set up environment
cp .env.example .env
# Edit .env with your QWEN_API_KEY

# Deploy with Docker
./deploy-docker.sh

# View logs
docker logs -f legalist_app
```

## Environment Variables

See `.env.example` for all available configuration:

| Variable | Required | Description |
|----------|----------|-------------|
| `QWEN_API_KEY` | Yes | DashScope API key for Qwen models |
| `DASHSCOPE_API_KEY` | No | Alias for `QWEN_API_KEY` |
| `QWEN_AUDIO_MODEL` | No | Single audio transcription model |
| `QWEN_AUDIO_MODELS` | No | Comma-separated fallback chain for audio |
| `QWEN_TTS_MODEL` | No | TTS model (default: `qwen3-tts-flash`) |
| `QWEN_TTS_VOICE` | No | TTS voice (options: Cherry, Serena, Ethan, Chloe) |

## Live Deployment

- **URL:** [http://47.237.180.168:8000](http://47.237.180.168:8000)
- **Mirror:** [https://codex-legalist.vercel.app/](https://codex-legalist.vercel.app/)
- **Method:** Docker on Alibaba Cloud ECS (Ubuntu 24.04)

## CI/CD

No CI/CD pipeline is currently configured. All deployments are manual via `deploy.sh` (local) or `deploy-docker.sh` (production). See above for actual manual steps.
