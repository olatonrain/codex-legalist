import os
import requests
import dashscope
import base64
from openai import OpenAI
from src.logger import get_logger

logger = get_logger(__name__)

def _set_key():
    """Sets the DashScope API key from environment."""
    key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise EnvironmentError("Neither QWEN_API_KEY nor DASHSCOPE_API_KEY is set in .env")
    dashscope.api_key = key
    # Route endpoints internationally if the workspace key is detected
    if key.startswith("sk-ws-"):
        dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
        dashscope.base_websocket_api_url = 'wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference'


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """
    Transcribes audio bytes using only Qwen audio/omni models on Qwen Cloud.
    """
    errors = []
    for model in _audio_model_candidates():
        try:
            text = _transcribe_with_qwen_audio_llm(audio_bytes, filename, model)
            if text:
                return text
            errors.append(f"{model}: returned no transcript.")
        except Exception as exc:
            errors.append(f"{model}: {exc}")

    raise RuntimeError(
        "No configured Qwen audio model could transcribe the file. "
        "Set QWEN_AUDIO_MODEL to an audio/omni model enabled on your Qwen Cloud account. "
        + " | ".join(errors)
    )


def _audio_model_candidates() -> list[str]:
    configured = os.getenv("QWEN_AUDIO_MODEL") or os.getenv("QWEN_AUDIO_MODELS")
    if configured:
        return [m.strip() for m in configured.split(",") if m.strip()]
    return [
        "qwen-omni-turbo",
        "qwen3-omni-flash",
        "qwen3-omni",
        "qwen-audio-turbo",
        "qwen2-audio-7b-instruct",
    ]


def _transcribe_with_qwen_audio_llm(audio_bytes: bytes, filename: str, model: str) -> str:
    api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise EnvironmentError("Neither QWEN_API_KEY nor DASHSCOPE_API_KEY is set in .env")

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    mime = f"audio/{suffix}"
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    # Qwen compatible-mode requires a full data URI, not bare base64
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{encoded}"

    # qwen-omni models require stream=True and explicit text modality
    is_omni = "omni" in model.lower()
    stream = is_omni
    extra = {"modalities": ["text"]} if is_omni else {}

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Transcribe this courtroom case-facts audio exactly. Return only the transcript text.",
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": data_uri,
                        "format": suffix,
                    },
                },
            ],
        }],
        temperature=0,
        stream=stream,
        **extra,
    )

    if stream:
        chunks = []
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                chunks.append(delta.content)
        return "".join(chunks).strip()

    return (response.choices[0].message.content or "").strip()


def generate_speech(text: str, voice: str = "Cherry") -> bytes:
    """
    Generates speech from text using Qwen-TTS on Qwen Cloud.
    """
    _set_key()
    try:
        from dashscope.audio.qwen_tts import SpeechSynthesizer as QwenSpeechSynthesizer
        res = QwenSpeechSynthesizer.call(
            model=os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash"),
            api_key=dashscope.api_key,
            text=text,
            voice=os.getenv("QWEN_TTS_VOICE", "Cherry")
        )
        if res.status_code == 200 and res.output and 'audio' in res.output and 'url' in res.output['audio']:
            return requests.get(res.output['audio']['url']).content
        else:
            logger.error(f"Qwen TTS Error: {res.message}")
            return b""
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return b""
