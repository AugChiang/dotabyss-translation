#!/usr/bin/env python3
"""
validate_coverage.py
=====================
在 CI 環境中執行 Masterdata 覆蓋率驗證。
若任何高優先 category 的覆蓋率低於門檻值，則以非零退出碼失敗。

用法（GitHub Actions）
----------------------
  python tools/validate_coverage.py [--strict]

  --strict  所有 category 都必須達標（預設只警告 non-critical category）

退出碼
------
  0  全部通過
  1  有 critical category 未達門檻
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

# 覆蓋率門檻（< 門檻則失敗）
THRESHOLDS: dict[str, float] = {
    "ability_descriptions": 85.0,   # 技能描述，高優先
    "names":                95.0,   # 角色名，高優先
    "titles":               90.0,   # 劇情標題
    "descriptions":         10.0,   # 劇情簡介（長文，門檻寬鬆）
    "items":                30.0,   # 道具說明
    "materials":            10.0,   # 素材名稱
    "ui_misc":              1.0,    # UI 雜項（基線）
    "mission":              0.0,    # 任務文字（非 critical）
    "facility":             0.0,    # 設施文字（非 critical）
    "dialogue":             0.0,    # 語音台詞（非 critical）
    "dictionary":           0.0,    # 圖鑑長文（非 critical）
    "another_name":         0.0,    # 角色第二名稱
}

CRITICAL = {"ability_descriptions", "names", "titles"}

MASTERDATA_BASE = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data"
MASTERDATA_API  = "https://api.github.com/repos/DotAbyss/Masterdata/contents/data"

# 欄位映射（同 masterdata_gap_report.py，此處精簡為核心 category）
FIELD_MAP = [
    ("m_characters",            "name",          "names"),
    ("m_ability_details",       "description",   "ability_descriptions"),
    ("m_character_action_skills","description",  "ability_descriptions"),
    ("m_items",                 "flavor_text",   "items"),
    ("m_weapons",               "flavor_text",   "items"),
    ("m_armors",                "flavor_text",   "items"),
    ("m_accessories",           "flavor_text",   "items"),
    ("m_items",                 "name",          "materials"),
    ("m_limited_items",         "name",          "materials"),
    ("m_weapons",               "name",          "ui_misc"),
    ("m_armors",                "name",          "ui_misc"),
    ("m_accessories",           "name",          "ui_misc"),
    ("m_novel_mains",           "title",         "titles"),
    ("m_novel_mains",           "description",   "descriptions"),
    ("m_character_profiles",    "flavor_text",   "descriptions"),
    ("m_chapter_quests",        "name",          "mission"),
    ("m_buildings",             "name",          "facility"),
    ("m_character_skins",       "serif",         "dialogue"),
    ("m_dictionary_worlds",     "title",         "dictionary"),
    ("m_dictionary_worlds",     "desciption",    "dictionary"),
    ("m_character_profiles",    "catchphrase",   "another_name"),
]

CATEGORY_PATHS = {
    "names":                ["names/zh_Hant.json"],
    "ability_descriptions": ["ability_descriptions/zh_Hant.json"],
    "titles":               ["titles/zh_Hant.json"],
    "descriptions":         ["descriptions/zh_Hant.json"],
    "another_name":         ["another_name/zh_Hant.json"],
    "items":                ["add-on/items/zh_Hant.json"],
    "materials":            ["other/materials/zh_Hant.json", "add-on/materials/zh_Hant.json"],
    "ui_misc":              ["other/ui_misc/zh_Hant.json", "add-on/ui_misc/zh_Hant.json"],
    "mission":              ["other/mission/zh_Hant.json", "add-on/mission/zh_Hant.json"],
    "facility":             ["other/facility/zh_Hant.json", "add-on/facility/zh_Hant.json"],
    "dialogue":             ["other/dialogue/zh_Hant.json", "add-on/dialogue/zh_Hant.json"],
    "dictionary":           ["add-on/dictionary/zh_Hant.json"],
    "another_name":         ["another_name/zh_Hant.json"],
}

JP_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_masterdata(translations_dir: Path) -> dict[str, set[str]]:
    try:
        listing = fetch_json(MASTERDATA_API)
    except Exception as e:
        print(f"[error] 無法列出 Masterdata: {e}", file=sys.stderr)
        sys.exit(2)

    files = {x["name"] for x in listing if x["name"].endswith(".json")}
    prefix_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for prefix, field, cat in FIELD_MAP:
        prefix_map[prefix].append((field, cat))

    result: dict[str, set[str]] = defaultdict(set)
    for fname in files:
        stem = fname[:-5]
        matched = [(p, fcs) for p, fcs in prefix_map.items() if stem == p]
        if not matched:
            continue
        try:
            data = fetch_json(f"{MASTERDATA_BASE}/{fname}")
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        all_fc = [(f, c) for _, fcs in matched for (f, c) in fcs]
        for row in data:
            if not isinstance(row, dict):
                continue
            for field, cat in all_fc:
                v = row.get(field)
                if isinstance(v, str) and v.strip() and JP_RE.search(v):
                    result[cat].add(v)
    return dict(result)


def load_existing(translations_dir: Path) -> dict[str, set[str]]:
    result = {}
    for cat, paths in CATEGORY_PATHS.items():
        keys: set[str] = set()
        for rel in paths:
            p = translations_dir / rel
            if p.exists():
                with p.open(encoding="utf-8-sig") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    keys |= set(d.keys())
        result[cat] = keys
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="所有 category 都必須達門檻值")
    parser.add_argument("--translations-dir", default=None)
    args = parser.parse_args()

    translations_dir = (
        Path(args.translations_dir)
        if args.translations_dir
        else Path(__file__).parent.parent / "translations"
    )

    print("=== Masterdata 覆蓋率驗證 ===")
    print("正在從 GitHub 取得 Masterdata...")
    ja_by_cat = extract_masterdata(translations_dir)
    existing = load_existing(translations_dir)

    failed_critical = []
    failed_non_critical = []

    print(f"\n{'Category':<25} {'覆蓋率':>8}  {'命中/總數':>12}  {'門檻':>8}  狀態")
    print("-" * 70)

    for cat in sorted(set(THRESHOLDS) & set(ja_by_cat)):
        total = len(ja_by_cat[cat])
        hit = len(ja_by_cat[cat] & existing.get(cat, set()))
        pct = hit / total * 100 if total else 100.0
        threshold = THRESHOLDS.get(cat, 0.0)
        ok = pct >= threshold
        status = "✓" if ok else "✗"
        is_crit = cat in CRITICAL
        print(f"  {cat:<23} {pct:>7.1f}%  {hit:>6}/{total:<6}  {threshold:>6.1f}%  {status}{'(critical)' if is_crit and not ok else ''}")
        if not ok:
            if is_crit or args.strict:
                failed_critical.append(cat)
            else:
                failed_non_critical.append(cat)

    print("-" * 70)
    if failed_non_critical:
        print(f"\n[warn] 以下 category 低於門檻（非 critical）：{failed_non_critical}")
    if failed_critical:
        print(f"\n[FAIL] 以下 critical category 低於門檻：{failed_critical}")
        sys.exit(1)
    else:
        print("\n[PASS] 所有 critical category 達標。")
        sys.exit(0)


if __name__ == "__main__":
    main()
