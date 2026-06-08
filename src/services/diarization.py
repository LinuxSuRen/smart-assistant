import numpy as np
from funasr import AutoModel


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class DiarizationProcessor:
    def __init__(self, model_name="iic/speech_campplus_sv_zh-cn_16k-common",
                 device="cpu", similarity_threshold=0.6):
        self.model = AutoModel(
            model=model_name,
            device=device,
            disable_pbar=True,
        )
        self.threshold = similarity_threshold
        self.known_speakers: dict = {}
        self.next_speaker_id = 0

    def extract_embedding(self, audio: np.ndarray) -> np.ndarray:
        if len(audio) < 1600:
            return np.zeros(192, dtype=np.float32)
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        try:
            result = self.model.generate(input=audio, input_len=len(audio))
            if result and len(result) > 0 and "spk_embedding" in result[0]:
                emb = np.array(result[0]["spk_embedding"], dtype=np.float32)
                return emb.flatten()
        except Exception:
            pass
        return np.zeros(192, dtype=np.float32)

    def identify_speaker(self, embedding: np.ndarray) -> str:
        if np.linalg.norm(embedding) == 0:
            return "SPEAKER_0"
        best_speaker = None
        best_similarity = -1.0
        for speaker_id, embeddings in self.known_speakers.items():
            avg_emb = np.mean(np.array(embeddings), axis=0)
            sim = _cosine_similarity(embedding, avg_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_speaker = speaker_id
        if best_similarity >= self.threshold and best_speaker is not None:
            self.known_speakers[best_speaker].append(embedding)
            if len(self.known_speakers[best_speaker]) > 10:
                self.known_speakers[best_speaker] = self.known_speakers[best_speaker][-10:]
            return best_speaker
        speaker_id = f"SPEAKER_{self.next_speaker_id}"
        self.known_speakers[speaker_id] = [embedding]
        self.next_speaker_id += 1
        return speaker_id

    def process(self, audio: np.ndarray) -> str:
        embedding = self.extract_embedding(audio)
        return self.identify_speaker(embedding)
