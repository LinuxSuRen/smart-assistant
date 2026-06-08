import asyncio
import numpy as np
from ..config import settings

MAX_BUFFER_SAMPLES = int(settings.sample_rate * settings.buffer_duration_seconds)


class TranscriptionPipeline:
    def __init__(self):
        from .vad import VADProcessor
        from .asr import ASRProcessor
        from .diarization import DiarizationProcessor
        from .llm import LLMProcessor
        from .tts import TTSProcessor

        self.vad = VADProcessor(
            threshold=settings.vad_threshold,
            min_speech_duration_ms=settings.vad_min_speech_duration_ms,
            min_silence_duration_ms=settings.vad_min_silence_duration_ms,
            speech_pad_ms=settings.vad_speech_pad_ms,
        )
        self.asr = ASRProcessor(
            model_name=settings.asr_model,
            device=settings.asr_device,
            ncpu=settings.asr_ncpu,
        )
        self.diar = DiarizationProcessor(
            model_name=settings.diar_model,
            device=settings.diar_device,
            similarity_threshold=settings.diar_similarity_threshold,
        )
        self.llm = LLMProcessor(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            system_prompt=settings.llm_system_prompt,
            max_history=settings.llm_max_history,
        )
        self.tts = TTSProcessor(voice=settings.tts_voice)

        self.sample_rate = settings.sample_rate
        self.buffer = np.array([], dtype=np.float32)
        self.processed_offset = 0.0
        self.lock = asyncio.Lock()

    async def feed_pcm(self, pcm_bytes: bytes) -> list:
        async with self.lock:
            return self._feed_pcm_sync(pcm_bytes)

    def _feed_pcm_sync(self, pcm_bytes: bytes) -> list:
        new_audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self.buffer = np.concatenate([self.buffer, new_audio])
        buffer_duration = len(self.buffer) / self.sample_rate
        segments = self.vad.detect_segments(self.buffer)
        results = []
        for seg in segments:
            seg_start = float(seg["start"])
            seg_end = float(seg["end"])
            if seg_end <= self.processed_offset:
                continue
            if seg_end + 0.3 > buffer_duration:
                continue
            seg_start = max(seg_start, self.processed_offset)
            start_idx = int(seg_start * self.sample_rate)
            end_idx = int(seg_end * self.sample_rate)
            if end_idx <= start_idx:
                continue
            seg_audio = self.buffer[start_idx:end_idx]
            asr_results = self.asr.transcribe(seg_audio)
            speaker = self.diar.process(seg_audio)
            for item in asr_results:
                text = item.get("text", "").strip()
                if not text:
                    continue
                results.append({
                    "speaker": speaker,
                    "text": text,
                    "start": round(seg_start + item.get("start", 0), 2),
                    "end": round(seg_start + item.get("end", len(seg_audio) / self.sample_rate), 2),
                })
            self.processed_offset = seg_end
        if self.processed_offset > 3.0:
            trim_samples = int((self.processed_offset - 3.0) * self.sample_rate)
            if trim_samples > 0 and trim_samples < len(self.buffer):
                self.buffer = self.buffer[trim_samples:]
                self.processed_offset -= (trim_samples / self.sample_rate)
        if len(self.buffer) > MAX_BUFFER_SAMPLES:
            excess = len(self.buffer) - MAX_BUFFER_SAMPLES
            self.buffer = self.buffer[excess:]
            self.processed_offset -= (excess / self.sample_rate)
            self.processed_offset = max(0.0, self.processed_offset)
        return results

    async def get_llm_response(self, text: str, speaker: str = "user", progress_cb=None) -> dict:
        return await self.llm.chat(text, speaker, progress_cb)

    async def get_tts_audio(self, text: str) -> bytes:
        return await self.tts.synthesize(text)

    def reset(self):
        self.buffer = np.array([], dtype=np.float32)
        self.processed_offset = 0.0
