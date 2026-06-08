"""Pre-download models to avoid first-run delays."""
import sys
sys.path.insert(0, "src")

from config import settings


def download_asr_model():
    print(f"Downloading ASR model: {settings.asr_model}...")
    from funasr import AutoModel
    model = AutoModel(
        model=settings.asr_model,
        device="cpu",
        disable_pbar=True,
        ncpu=settings.asr_ncpu,
    )
    print("ASR model ready.")
    return model


def download_diar_model():
    print(f"Downloading diarization model: {settings.diar_model}...")
    from funasr import AutoModel
    model = AutoModel(
        model=settings.diar_model,
        device="cpu",
        disable_pbar=True,
    )
    print("Diarization model ready.")
    return model


def check_silero_vad():
    print("Checking Silero VAD...")
    from silero_vad import load_silero_vad
    model = load_silero_vad()
    print("Silero VAD ready.")
    return model


if __name__ == "__main__":
    print("=" * 50)
    print("Downloading models for Smart Assistant")
    print("=" * 50)
    check_silero_vad()
    download_asr_model()
    download_diar_model()
    print("=" * 50)
    print("All models downloaded successfully!")
    print("=" * 50)
