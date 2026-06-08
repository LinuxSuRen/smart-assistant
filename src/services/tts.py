import tempfile
import os


class TTSProcessor:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        self.voice = voice
        self._edge_tts = None

    @property
    def available(self) -> bool:
        if self._edge_tts is None:
            try:
                import edge_tts
                self._edge_tts = edge_tts
            except ImportError:
                self._edge_tts = False
        return bool(self._edge_tts)

    async def synthesize(self, text: str) -> bytes:
        if not text.strip() or not self.available:
            return b""
        communicate = self._edge_tts.Communicate(text, self.voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
        try:
            await communicate.save(temp_path)
            with open(temp_path, "rb") as f:
                audio_data = f.read()
            return audio_data
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
