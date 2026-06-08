import json
from openai import AsyncOpenAI
from .tools import TOOL_DEFINITIONS, execute_tool

MAX_TOOL_ROUNDS = 5


class LLMProcessor:
    def __init__(self, model="deepseek-v4-pro", api_key="", base_url="",
                 system_prompt="You are a helpful assistant. Be concise.", max_history=20):
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.history: list = []
        self.tools = TOOL_DEFINITIONS

        if base_url and not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key and base_url else None

    async def _call_llm(self, messages: list) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message

    async def chat(self, user_message: str, speaker: str = "user", progress_cb=None) -> dict:
        if not user_message.strip():
            return {"text": "", "tool_calls": []}
        if not self.client:
            return {"text": "[LLM not configured]", "tool_calls": []}

        self.history.append({"role": "user", "content": f"[{speaker}]: {user_message}"})
        messages = [{"role": "system", "content": self.system_prompt}] + self.history[-self.max_history:]
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-(self.max_history * 2):]

        all_tool_calls = []
        end_conversation = False

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                msg = await self._call_llm(messages)
                messages.append(msg)

                if not msg.tool_calls:
                    reply = msg.content or ""
                    if reply:
                        self.history.append({"role": "assistant", "content": reply})
                    return {"text": reply, "tool_calls": all_tool_calls, "end_conversation": end_conversation}

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    if progress_cb:
                        await progress_cb({
                            "type": "tool_start",
                            "name": name,
                            "arguments": args,
                            "call_id": tc.id,
                        })
                    result = await execute_tool(name, args)
                    if name == "end_conversation" and result.get("end_conversation"):
                        end_conversation = True
                    if progress_cb:
                        await progress_cb({
                            "type": "tool_result",
                            "name": name,
                            "call_id": tc.id,
                            "success": result.get("success", False),
                            "output": result.get("output", "")[:2000],
                        })
                    all_tool_calls.append({
                        "id": tc.id,
                        "name": name,
                        "arguments": args,
                        "result": result,
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            reply = "[Max tool rounds reached]"
            self.history.append({"role": "assistant", "content": reply})
            return {"text": reply, "tool_calls": all_tool_calls, "end_conversation": end_conversation}

        except Exception as e:
            return {"text": f"[LLM Error: {e}]", "tool_calls": all_tool_calls, "end_conversation": end_conversation}

    def clear_history(self):
        self.history = []

    def get_history_text(self) -> str:
        lines = []
        for entry in self.history:
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role == "user":
                lines.append(content)
            elif role == "assistant":
                lines.append(f"Assistant: {content}")
        return "\n".join(lines)
