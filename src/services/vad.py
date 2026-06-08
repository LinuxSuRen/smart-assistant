import numpy as np
from silero_vad import load_silero_vad, get_speech_timestamps


class VADProcessor:
    def __init__(self, threshold=0.5, min_speech_duration_ms=300,
                 min_silence_duration_ms=500, speech_pad_ms=200):
        self.model = load_silero_vad()
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms

    def detect_segments(self, audio: np.ndarray) -> list:
        if len(audio) < self.min_speech_duration_ms * 16:
            return []
        timestamps = get_speech_timestamps(
            audio,
            self.model,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms,
            return_seconds=True,
        )
        for ts in timestamps:
            ts["start"] = max(0, ts["start"] - self.speech_pad_ms / 1000.0)
            ts["end"] = ts["end"] + self.speech_pad_ms / 1000.0
        return timestamps
