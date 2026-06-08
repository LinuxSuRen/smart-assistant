import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ASR (SenseVoice)
    asr_model: str = "iic/SenseVoiceSmall"
    asr_device: str = "cpu"
    asr_ncpu: int = 4

    # VAD (Silero)
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 300
    vad_min_silence_duration_ms: int = 500
    vad_speech_pad_ms: int = 200

    # Speaker Diarization (CAM++)
    diar_model: str = "iic/speech_campplus_sv_zh-cn_16k-common"
    diar_device: str = "cpu"
    diar_similarity_threshold: float = 0.6

    # LLM (LiteLLM)
    llm_model: str = "deepseek-v4-pro"
    llm_api_key: str = os.environ.get("LITELLM_API_KEY", "")
    llm_base_url: str = os.environ.get("LITELLM_BASE_URL", "")
    llm_system_prompt: str = (
        "You are a helpful voice assistant with access to system tools. "
        "You can run shell commands, read files, and list directories to help the user. "
        "Use tools when you need factual information or system access. "
        "Respond concisely in 1-3 sentences. Format command output nicely. "
        "If the user speaks Chinese, respond in Chinese. If English, respond in English."
    )
    llm_max_history: int = 20

    # TTS (edge-tts)
    tts_voice: str = "zh-CN-XiaoxiaoNeural"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    sample_rate: int = 16000

    # Audio buffer
    buffer_duration_seconds: float = 10.0

    model_config = {"env_prefix": "SA_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
