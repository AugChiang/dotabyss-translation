#!/usr/bin/env python3
"""用 Ollama 翻譯 import_ability_result.json 中仍缺的 ability 條目，保留所有 {[...]} 佔位符。"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

SYSTEM_PROMPT = (
    "你是手機遊戲《ドットアビス》的日譯繁體中文（台灣）在地化譯者。"
    "請把使用者給出的日文翻譯成台灣慣用的繁體中文，只輸出譯文本身，不要解釋、不要加引號、不要輸出英文或簡體字。"
    "最重要：原文中形如 {[DAMAGE.DAMAGE_PERCENT]}、{[PRJCTL.LAND.DAMAGE.DAMAGE_PERCENT]}、"
    "{[RECOVER.HEAL_PERCENT]} 等 {[...]} 佔位符必須連同花括號原樣保留，位置和數量都不能改；"
    "形如 {0} {1} 的花括號佔位符、<...> 標籤、【】符號、\\n 換行也都原樣保留。"
    "術語：紋章=紋章，衝撃=衝擊，情熱=熱情，会心=會心，スキル=技能，マナ=魔力，"
    "バリア=護盾，付与=附加，上昇=提升，永続=永續，ノックバック=擊退，喪失=喪失，"
    "凍結=凍結，石化=石化，魅了=魅惑，挑発=挑釁，召喚=召喚。"
)

FEW_SHOT = [
    {"role": "user", "content": "最も近い敵1体に【4HIT / 合計{[PRJCTL.LAND.DAMAGE.DAMAGE_PERCENT]}】ダメージ / 自身に紋章：情熱を【1】付与"},
    {"role": "assistant", "content": "對最近的1個敵人造成【4HIT / 合計{[PRJCTL.LAND.DAMAGE.DAMAGE_PERCENT]}】傷害 / 對自身施加紋章：熱情【1】"},
    {"role": "user", "content": "ダメージ倍率が【{[DAMAGE.DAMAGE_PERCENT]}】に変化"},
    {"role": "assistant", "content": "傷害倍率變為【{[DAMAGE.DAMAGE_PERCENT]}】"},
]

PLACEHOLDER_RE = re.compile(r"\{\[[^\]]+\][^}]*\}")


def extract_placeholders(text: str) -> list[str]:
    return PLACEHOLDER_RE.findall(text)


def ollama_translate(ja: str, endpoint: str, model: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *FEW_SHOT, {"role": "user", "content": ja}]
    body = json.dumps({"model": model, "temperature": 0, "stream": False, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    zh = data["choices"][0]["message"]["content"].strip()
    if zh.startswith('"') and zh.endswith('"'):
        zh = zh[1:-1]
    return zh


def placeholders_ok(ja: str, zh: str) -> bool:
    for ph in extract_placeholders(ja):
        if ph not in zh:
            return False
    return True


def main() -> None:
    root = Path(__file__).parent.parent
    result_path = root / "reports" / "import_ability_result.json"
    trans_path = root / "translations" / "ability_descriptions" / "zh_Hant.json"
    endpoint = "http://127.0.0.1:11434/v1/chat/completions"
    model = "qwen2.5:3b"

    result = json.loads(result_path.read_text(encoding="utf-8"))
    target = json.loads(trans_path.read_text(encoding="utf-8-sig"))

    keys = [k for k in result["still_missing_keys"] if k not in target]
    print(f"待翻譯: {len(keys)} 條")

    added = 0
    for i, ja in enumerate(keys, 1):
        zh = None
        for attempt in range(3):
            try:
                candidate = ollama_translate(ja, endpoint, model)
                if placeholders_ok(ja, candidate):
                    zh = candidate
                    break
                print(f"  [{i}/{len(keys)}] 佔位符缺失，重試 ({attempt+1}/3)...")
            except Exception as e:
                print(f"  [{i}/{len(keys)}] 錯誤: {e}，重試...")
                time.sleep(2)
        if not zh:
            print(f"  [FAIL] {ja[:60]}...")
            continue
        target[ja] = zh
        added += 1
        print(f"  [{i}/{len(keys)}] OK")
        time.sleep(0.1)

    trans_path.write_text(json.dumps(target, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"\n完成：新增 {added}/{len(keys)} 條 → 總計 {len(target)} 條")


if __name__ == "__main__":
    main()
