import asyncio
import re

MAX_CHUNK_CHARS = 3000
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？\n])\s*")


def _split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text.strip()]

    sentences = SENTENCE_BOUNDARY.split(text)
    chunks = []
    current = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip() if current else s
        else:
            if current:
                chunks.append(current)
            if len(s) > max_chars:
                for i in range(0, len(s), max_chars):
                    chunks.append(s[i : i + max_chars].strip())
                current = ""
            else:
                current = s

    if current:
        chunks.append(current)

    return chunks


async def summarize_text(client, model: str, text: str) -> str:
    if not text.strip():
        return "No text to summarize."

    chunks = _split_text(text)

    if len(chunks) == 1:
        return await _summarize_chunk(client, model, chunks[0])

    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        summary = await _summarize_chunk(client, model, chunk, f" (part {i + 1}/{len(chunks)})")
        chunk_summaries.append(summary)

    combined = "\n\n".join(chunk_summaries)
    if len(combined) <= MAX_CHUNK_CHARS:
        return await _summarize_chunk(client, model, combined, " (combining summaries)")

    return await summarize_text(client, model, combined)


async def _summarize_chunk(client, model: str, text: str, label: str = "") -> str:
    prompt = (
        "Summarize the following conversation transcript concisely. "
        "Capture key points, decisions, and action items. "
        "Write the summary in the same language as the transcript."
        + label
    )
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.5,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""
