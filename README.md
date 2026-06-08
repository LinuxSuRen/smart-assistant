# Smart Assistant

Real-time speech recognition + speaker diarization + AI voice assistant with tool calling. Pure CPU, runs entirely locally except for LLM and TTS.

## Features

- **Real-time ASR** — SenseVoice-small for Chinese + English mixed speech
- **Speaker Diarization** — CAM++ embeddings, identifies who is speaking
- **VAD** — Silero voice activity detection with configurable thresholds
- **AI Dialogue** — LLM-powered responses with conversation memory (OpenAI-compatible API)
- **Voice Output** — edge-tts text-to-speech synthesis
- **Tool Calling** — LLM can execute shell commands, read files, list directories, and delegate coding tasks to opencode
- **Interrupt** — Speak while AI is talking to cut it off
- **Summarize** — One-click transcript summarization with auto-chunking for long text
- **Web UI** — Browser-based interface with microphone capture, speaker colors, timeline ruler

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
- `LITELLM_API_KEY` — API key for the LLM provider
- `LITELLM_BASE_URL` — LLM API base URL (e.g., `http://your-llm-server:4000`)

### 3. Download models

```bash
python scripts/download_models.py
```

Models (~1GB total):
- SenseVoiceSmall (ASR)
- CAM++ (speaker diarization)
- Silero VAD

### 4. Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser. Click "Start Recording" and speak.

## Modes

| Mode | Description |
|------|-------------|
| **Dialogue** (default) | Transcribe speech + get AI voice response |
| **Transcribe Only** | Transcribe without AI responses |

## Tools

The AI assistant can use these tools:

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands (dangerous patterns blocked) |
| `read_file` | Read file contents (max 50KB) |
| `list_directory` | List directory entries |
| `opencode_run` | Delegate coding tasks to opencode |

## Architecture

```
Browser (Web Audio API) → WebSocket → FastAPI Server
                                       ├─ VAD (Silero)
                                       ├─ ASR (SenseVoice)
                                       ├─ Diarization (CAM++)
                                       ├─ LLM (OpenAI-compatible)
                                       └─ TTS (edge-tts)
```

## Configuration

Key settings in `src/config.py` (override via env vars with `SA_` prefix):

| Setting | Default | Description |
|---------|---------|-------------|
| `asr_model` | `iic/SenseVoiceSmall` | ASR model |
| `vad_threshold` | `0.5` | VAD sensitivity |
| `llm_model` | `deepseek-v4-pro` | LLM model name |
| `sample_rate` | `16000` | Audio sample rate |
| `tts_voice` | `zh-CN-XiaoxiaoNeural` | TTS voice |

## License

MIT
