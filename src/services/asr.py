import re
import numpy as np
from funasr import AutoModel

_SENSEVOICE_TAG_RE = re.compile(r"<\|[^|]*\|>")


class ASRProcessor:
    def __init__(self, model_name="iic/SenseVoiceSmall", device="cpu", ncpu=4):
        self.model = AutoModel(
            model=model_name,
            device=device,
            disable_pbar=True,
            ncpu=ncpu,
        )
        self.sample_rate = 16000

    def transcribe(self, audio: np.ndarray) -> list:
        if len(audio) < 160:
            return [{"text": "", "start": 0, "end": 0}]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        duration = len(audio) / self.sample_rate
        try:
            result = self.model.generate(input=audio, input_len=len(audio))
            if result and len(result) > 0:
                raw = result[0].get("text", "")
                text = _SENSEVOICE_TAG_RE.sub("", raw).strip()
                if text:
                    return [{"text": text, "start": 0, "end": duration}]
        except Exception:
            pass
        return [{"text": "", "start": 0, "end": duration}]
