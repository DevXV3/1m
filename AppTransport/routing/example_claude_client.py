"""Example: let Claude answer transport questions using the routing tools.

Runs a manual tool-use loop against the Claude API. The same TOOLS/dispatch
layer also works with a local model (e.g. Qwythos via an OpenAI-compatible
endpoint) — only this client file is Anthropic-specific.

    pip install anthropic
    python example_claude_client.py "ส่งปูนจากอำเภอเมืองอุบล ไปอำเภอวารินชำราบ ใช้รถโม่ ค่าเท่าไหร่"
"""
import sys
from pathlib import Path

import anthropic

from apptransport_routing.tools import TOOLS, ToolRunner

CACHE = Path(__file__).resolve().parent / "cache"
MODEL = "claude-opus-4-8"  # swap to "claude-fable-5" for the most capable model

SYSTEM = (
    "คุณเป็นผู้ช่วยวางแผนขนส่งของบริษัทวันเอ็ม (คอนกรีต/วัสดุก่อสร้าง จ.อุบลราชธานี). "
    "ใช้เครื่องมือที่มีเพื่อค้นสถานที่ หาเส้นทาง และคำนวณค่าขนส่งแบบออฟไลน์ "
    "แล้วสรุปเป็นภาษาไทยให้พนักงานเข้าใจง่าย (ระยะทาง กม., เวลาโดยประมาณ, ค่าขนส่งบาท)."
)


def main() -> None:
    question = " ".join(sys.argv[1:]) or "หาเส้นทางและค่าขนส่งจากอุบลราชธานีไปนครราชสีมา รถ 10 ล้อ"
    runner = ToolRunner.from_cache(CACHE)
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                out = runner.dispatch(block.name, block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": __import__("json").dumps(out, ensure_ascii=False),
                })
        messages.append({"role": "user", "content": results})

    print(next((b.text for b in response.content if b.type == "text"), ""))


if __name__ == "__main__":
    main()
