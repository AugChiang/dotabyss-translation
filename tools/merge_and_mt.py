#!/usr/bin/env python3
"""
merge_and_mt.py
===============
1. 將 other/{category}/ 的精翻譯文合併到 add-on/{category}/（other 優先，不刪除 other）
2. 讀取 reports/draft_{category}.json，用 Ollama 機翻缺口，寫入對應目標：

   draft → 目標路徑
   ─────────────────────────────────────────
   ui_misc, materials, mission, facility,
   dialogue, dictionary          → other/{category}/
   items                         → add-on/items/
   descriptions, another_name,
   names, ability_descriptions   → translations/{category}/

用法
----
  # 只做合併（不機翻）
  python tools/merge_and_mt.py --merge-only

  # 機翻全部缺口（Ollama，可中斷後 --resume 續跑）
  python tools/merge_and_mt.py

  # 只翻譯指定 category
  python tools/merge_and_mt.py --category ui_misc

  # 自訂模型
  python tools/merge_and_mt.py --model qwen2.5:3b --endpoint http://127.0.0.1:11434/v1/chat/completions
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── 與 AbyssMod MachineTranslator 相同的繁中提示詞 ──────────────────────────
SYSTEM_PROMPT_HANT = (
    "你是手機遊戲《ドットアビス》的日譯繁體中文（台灣）在地化譯者。"
    "請把使用者給出的日文翻譯成台灣慣用的繁體中文，只輸出譯文本身，不要解釋、不要加引號、不要輸出英文或簡體字。"
    "最重要：原文中形如 {0} {1} 的花括號佔位符必須連同花括號原樣保留，位置和數量都不能改；"
    "<...> 標籤、【】符號、\\n 換行也都原樣保留。"
    "術語：紋章=紋章，衝撃=衝擊，情熱=熱情，会心=會心，スキル=技能，マナ=魔力，"
    "バリア=護盾，付与=附加，上昇=提升，永続=永續，リトライ=重試，パーティ=隊伍，ソート=排序。"
)

FEW_SHOT = [
    {"role": "user", "content": "自身の攻撃力が【{0}】上昇"},
    {"role": "assistant", "content": "自身攻擊力提升【{0}】"},
    {"role": "user", "content": "紋章：衝撃を【{0}】付与 / 自身に最大HP【{1}】分の回復"},
    {"role": "assistant", "content": "附加紋章：衝擊【{0}】 / 回復自身最大HP的【{1}】"},
]

# other/ 內所有子類別（合併到 add-on）
OTHER_CATEGORIES = [
    "ui_misc", "materials", "mission", "facility", "dialogue",
    "equipment_effect", "bar", "abyss_code", "system",
]

# draft 檔名 → (prefix, category)  prefix="" 表示頂層 translations/{cat}/
DRAFT_TARGETS: dict[str, tuple[str, str]] = {
    "ui_misc":              ("other",  "ui_misc"),
    "materials":            ("other",  "materials"),
    "mission":              ("other",  "mission"),
    "facility":             ("other",  "facility"),
    "dialogue":             ("other",  "dialogue"),
    "dictionary":           ("other",  "dictionary"),
    "items":                ("add-on", "items"),
    "descriptions":         ("",       "descriptions"),
    "another_name":         ("",       "another_name"),
    "names":                ("",       "names"),
    "ability_descriptions": ("",       "ability_descriptions"),
}

UNRESOLVED_RE = re.compile(
    r"\{\[(?:PRJCTL|AOE|RECOVER|DAMAGE|ABNORMAL|MANA|ATTACK|IMPACT|BARRIER|CRITICALUP|"
    r"IMPACTSUCCEED|LAND|THROW|ATTACKUP|SUMMON|SKILLDAMAGE|ZEAL|SUMMON_MIRROR|SUMMON_SERVANT|DRAIN)"
    r"[\.\w:]*\][^}]*\}"
)

BATCH_MAX_CHARS = 60   # 短句可批次
BATCH_SIZE = 8


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def target_path(translations_dir: Path, prefix: str, category: str) -> Path:
    if prefix:
        return translations_dir / prefix / category / "zh_Hant.json"
    return translations_dir / category / "zh_Hant.json"


def merge_other_to_addon(translations_dir: Path) -> None:
    print("=== Phase 1: 合併 other/ → add-on/（精翻優先）===")
    for cat in OTHER_CATEGORIES:
        other_p = translations_dir / "other" / cat / "zh_Hant.json"
        addon_p = translations_dir / "add-on" / cat / "zh_Hant.json"
        if not other_p.exists():
            continue
        other = load_json(other_p)
        addon = load_json(addon_p)
        before = len(addon)
        merged = {**addon, **other}  # other 覆蓋同 key
        save_json(addon_p, merged)
        added = len(merged) - before
        print(f"  add-on/{cat}: {before} → {len(merged)} (+{added} from other)")


def ollama_chat(endpoint: str, model: str, messages: list[dict], timeout: int = 180) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "stream": False,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return clean_translation(content)


def clean_translation(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    # 去掉模型可能加的引號
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("「") and text.endswith("」")):
        text = text[1:-1]
    return text.strip()


def translate_single(endpoint: str, model: str, ja: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT_HANT}]
    messages.extend(FEW_SHOT)
    messages.append({"role": "user", "content": ja})
    return ollama_chat(endpoint, model, messages)


def translate_batch(endpoint: str, model: str, items: list[str]) -> list[str]:
    """批次翻譯短句，回傳與 items 等長的譯文列表。"""
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(items))
    prompt = (
        f"請將以下 {len(items)} 行日文各別翻譯成台灣繁體中文。"
        f"只輸出 {len(items)} 行譯文，每行開頭保留編號（1. 2. ...），不要其他說明。\n\n"
        + numbered
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT_HANT}]
    messages.append({"role": "user", "content": prompt})
    raw = ollama_chat(endpoint, model, messages, timeout=300)
    results: list[str] = []
    for i, ja in enumerate(items):
        # 解析 "N. 譯文" 格式
        m = re.search(rf"^{i+1}\.\s*(.+)$", raw, re.MULTILINE)
        if m:
            results.append(clean_translation(m.group(1)))
        else:
            # fallback 單條
            results.append(translate_single(endpoint, model, ja))
    return results


def collect_existing_keys(translations_dir: Path, prefix: str, category: str) -> set[str]:
    """收集目標路徑 + add-on 同類別（若目標是 other）的已有 key。"""
    keys: set[str] = set()
    keys |= set(load_json(target_path(translations_dir, prefix, category)).keys())
    if prefix == "other":
        keys |= set(load_json(target_path(translations_dir, "add-on", category)).keys())
    return keys


def load_checkpoint(path: Path) -> dict[str, str]:
    if path.exists():
        return load_json(path)
    return {}


def process_category(
    cat: str,
    translations_dir: Path,
    reports_dir: Path,
    endpoint: str,
    model: str,
    resume: bool,
) -> int:
    draft_p = reports_dir / f"draft_{cat}.json"
    if not draft_p.exists():
        print(f"  [skip] 無 draft_{cat}.json")
        return 0

    if cat not in DRAFT_TARGETS:
        print(f"  [skip] 未定義目標: {cat}")
        return 0

    prefix, target_cat = DRAFT_TARGETS[cat]
    out_p = target_path(translations_dir, prefix, target_cat)
    ckpt_p = reports_dir / f"mt_progress_{cat}.json"

    draft = load_json(draft_p)
    existing = collect_existing_keys(translations_dir, prefix, target_cat)
    target = load_json(out_p)
    progress = load_checkpoint(ckpt_p) if resume else {}

    # 待翻譯 key：draft 中空 value、不在 existing、不在 target、不在 progress
    todo: list[str] = []
    for ja, val in draft.items():
        if val:  # draft 已有譯文
            if ja not in target:
                target[ja] = val
            continue
        if UNRESOLVED_RE.search(ja):
            continue
        if ja in existing or ja in target or ja in progress:
            continue
        todo.append(ja)

    if not todo:
        print(f"  {cat}: 無需機翻（已全部覆蓋）")
        target.update(progress)
        save_json(out_p, target)
        return 0

    print(f"  {cat}: 待機翻 {len(todo)} 條 → {out_p.relative_to(translations_dir.parent)}")

    translated = 0
    i = 0
    while i < len(todo):
        # 嘗試批次（短句）
        batch: list[str] = []
        while i < len(todo) and len(batch) < BATCH_SIZE:
            s = todo[i]
            if "\n" in s or len(s) > BATCH_MAX_CHARS:
                break
            batch.append(s)
            i += 1

        if batch:
            try:
                zh_list = translate_batch(endpoint, model, batch)
                for ja, zh in zip(batch, zh_list):
                    if zh:
                        progress[ja] = zh
                        target[ja] = zh
                        translated += 1
                save_json(ckpt_p, progress)
                save_json(out_p, target)
                print(f"    批次 {translated}/{len(todo)} ...", end="\r")
                time.sleep(0.05)
            except Exception as e:
                print(f"\n    [warn] 批次失敗: {e}，改單條重試")
                i -= len(batch)
                batch = []

        if i < len(todo) and (not batch or len(batch) < BATCH_SIZE):
            ja = todo[i]
            i += 1
            try:
                zh = translate_single(endpoint, model, ja)
                if zh:
                    progress[ja] = zh
                    target[ja] = zh
                    translated += 1
                if translated % 5 == 0:
                    save_json(ckpt_p, progress)
                    save_json(out_p, target)
                    print(f"    進度 {translated}/{len(todo)} ...", end="\r")
                time.sleep(0.05)
            except Exception as e:
                print(f"\n    [error] 翻譯失敗: {ja[:40]!r} → {e}")
                time.sleep(2)

    save_json(out_p, target)
    print(f"\n  {cat}: 完成，新增 {translated} 條")
    return translated


def main() -> None:
    parser = argparse.ArgumentParser(description="合併 other→add-on 並用 Ollama 機翻 draft")
    parser.add_argument("--merge-only", action="store_true", help="只做合併，不機翻")
    parser.add_argument("--category", help="只處理指定 category")
    parser.add_argument("--no-resume", action="store_true", help="忽略 mt_progress_*.json 進度檔")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/v1/chat/completions")
    parser.add_argument("--translations-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    translations_dir = Path(args.translations_dir) if args.translations_dir else root / "translations"
    reports_dir = Path(args.reports_dir) if args.reports_dir else root / "reports"

    merge_other_to_addon(translations_dir)

    if args.merge_only:
        print("\n--merge-only，跳過機翻。")
        return

    cats = [args.category] if args.category else list(DRAFT_TARGETS.keys())
    print("\n=== Phase 2: Ollama 機翻 draft → 目標路徑 ===")
    print(f"  模型: {args.model}")
    print(f"  端點: {args.endpoint}")

    total = 0
    for cat in cats:
        n = process_category(
            cat, translations_dir, reports_dir,
            args.endpoint, args.model,
            resume=not args.no_resume,
        )
        total += n

    print(f"\n機翻合計新增: {total} 條")
    print("完成後請執行: python tools/rebuild_manifest.py")


if __name__ == "__main__":
    main()
