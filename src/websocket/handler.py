import asyncio
import base64
import json
import threading
import time
import traceback
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_pipeline = None
_pipeline_lock = threading.Lock()


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                from ..services.pipeline import TranscriptionPipeline
                _pipeline = TranscriptionPipeline()
    return _pipeline


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pipeline = _get_pipeline()
    mode = "dialogue"
    cooldown_until = 0.0
    processing_tts = False
    current_tts_task = None

    async def send_json(msg):
        try:
            await websocket.send_json(msg)
        except Exception:
            pass

    async def process_llm_tts(text, speaker):
        nonlocal cooldown_until, processing_tts
        processing_tts = True
        cooldown_until = time.time() + 60.0
        await send_json({"type": "busy", "status": True})

        async def tool_progress(evt):
            await send_json(evt)

        try:
            reply = await pipeline.get_llm_response(text, speaker, progress_cb=tool_progress)
            reply_text = reply.get("text", "") if isinstance(reply, dict) else str(reply)
            if reply_text:
                tts_bytes = await pipeline.get_tts_audio(reply_text)
                tts_b64 = base64.b64encode(tts_bytes).decode() if tts_bytes else ""
                await send_json({"type": "response", "text": reply_text, "audio": tts_b64})
        except asyncio.CancelledError:
            pipeline.reset()
            raise
        except Exception as e:
            await send_json({"type": "error", "message": f"LLM/TTS error: {e}"})

        cooldown_until = time.time() + 8.0
        pipeline.reset()
        processing_tts = False

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            msg_type = data.get("type", "")

            if msg_type == "mode":
                new_mode = data.get("mode", "transcribe")
                mode = new_mode if new_mode in ("transcribe", "dialogue") else "dialogue"
                await send_json({"type": "mode_set", "mode": mode})

            elif msg_type == "audio":
                now = time.time()
                pcm_b64 = data.get("data", "")
                if not pcm_b64:
                    continue
                pcm_bytes = base64.b64decode(pcm_b64)
                results = await pipeline.feed_pcm(pcm_bytes)

                if now < cooldown_until:
                    if results:
                        if current_tts_task and not current_tts_task.done():
                            current_tts_task.cancel()
                            current_tts_task = None
                            await send_json({"type": "interrupt"})
                        cooldown_until = 0.0
                        processing_tts = False
                        pipeline.reset()
                        await send_json({"type": "busy", "status": False})
                    continue

                cooldown_until = max(0.0, cooldown_until)
                await send_json({"type": "busy", "status": False})

                for result in results:
                    await send_json({
                        "type": "transcript",
                        "speaker": result["speaker"],
                        "text": result["text"],
                        "start": result["start"],
                        "end": result["end"],
                    })
                    if mode == "dialogue":
                        current_tts_task = asyncio.create_task(
                            process_llm_tts(result["text"], result["speaker"])
                        )

            elif msg_type == "reset":
                if current_tts_task and not current_tts_task.done():
                    current_tts_task.cancel()
                    current_tts_task = None
                pipeline.reset()
                cooldown_until = 0.0
                processing_tts = False
                await send_json({"type": "reset_ack"})
                await send_json({"type": "busy", "status": False})

            elif msg_type == "tts_end":
                if processing_tts:
                    cooldown_until = time.time() + 0.5
                    processing_tts = False
                    await send_json({"type": "busy", "status": False})

            elif msg_type == "summarize":
                if not pipeline.llm.client:
                    await send_json({"type": "error", "message": "LLM not configured"})
                    continue
                text = data.get("text", "")
                if not text.strip():
                    await send_json({"type": "summary", "text": "No text to summarize."})
                    continue
                await send_json({"type": "summarizing"})
                try:
                    from ..services.summarizer import summarize_text
                    result = await summarize_text(
                        pipeline.llm.client, pipeline.llm.model, text
                    )
                    await send_json({"type": "summary", "text": result})
                except Exception as e:
                    await send_json({"type": "error", "message": f"Summarize error: {e}"})

            elif msg_type == "stop":
                if current_tts_task and not current_tts_task.done():
                    current_tts_task.cancel()
                    current_tts_task = None
                await send_json({"type": "stopped"})
                break

    except WebSocketDisconnect:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
    except Exception as e:
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
