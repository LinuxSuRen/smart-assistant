import re
import tempfile
import os


_MD_PATTERNS = [
    (re.compile(r"\*\*\*(.+?)\*\*\*"), r"\1"),   # ***bold italic***
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),         # **bold**
    (re.compile(r"__(.+?)__"), r"\1"),             # __underline__
    (re.compile(r"\*(.+?)\*"), r"\1"),             # *italic*
    (re.compile(r"_(.+?)_"), r"\1"),               # _italic_
    (re.compile(r"~~(.+?)~~"), r"\1"),             # ~~strikethrough~~
    (re.compile(r"`(.+?)`"), r"\1"),               # `code`
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""), # headings
    (re.compile(r"^[-*+]\s+", re.MULTILINE), ""),  # list markers
    (re.compile(r"^\d+\.\s+", re.MULTILINE), ""),  # ordered list markers
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # [text](link)
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1"), # ![alt](image)
    (re.compile(r"^>\s+", re.MULTILINE), ""),      # blockquotes
]


def strip_markdown(text: str) -> str:
    for pattern, replacement in _MD_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


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
        speak_text = strip_markdown(text)
        if not speak_text:
            return b""
        communicate = self._edge_tts.Communicate(speak_text, self.voice)
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
