#!/usr/bin/env python3
"""
import_ability_gaps.py
======================
補齊 ability_descriptions 中因 {[...]} 佔位符被誤跳過的缺口：

1. BepInEx/.../dump/contrib/ability_descriptions_zh_Hans.json（社群精翻，含佔位符）
   → OpenCC s2twp 轉繁中
2. reports/auto_ability_descriptions.json（先前模板機翻，無佔位符句）

只新增 key，不覆蓋既有 zh_Hant 條目。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import opencc
except ImportError:
    raise SystemExit("請安裝 opencc-python-reimplemented: pip install opencc-python-reimplemented")

# 簡體 contrib 用語 → 與 repo 既有 zh_Hant 風格對齊（OpenCC 後補強）
POST_FIX: list[tuple[str, str]] = [
    ("附加纹章", "施加紋章"),   # 既有 numeric 條目多用「施加」
    ("附加紋章", "施加紋章"),
    ("为自身", "對自身"),
    ("為自身", "對自身"),
    ("为目标", "對目標"),
    ("為目標", "對目標"),
    ("为方", "對方"),           # 兜底
    ("为最近", "對最近"),
    ("为HP", "對HP"),
    ("为以", "對以"),
    ("为火", "對火"),
    ("为光", "對光"),
    ("为随机", "對隨機"),
    ("为最远", "對最遠"),
    ("为我方", "對我方"),
    ("对以", "對以"),           # OpenCC 可能漏掉
    ("名敌人", "個敵人"),
    ("名我方", "個友方"),
    ("暗・无", "暗・無"),
    ("暗·无", "暗·無"),
    ("无属性", "無屬性"),
    ("·无", "·無"),
    ("回复", "回覆"),
    ("并回复", "並回覆"),
    ("并为", "並對"),
    ("并充能", "並充能"),
    ("并为目标", "並對目標"),
    ("伤害倍率", "傷害倍率"),
    ("回复倍率", "回覆倍率"),
    ("会心率提升", "會心率UP"),
    ("攻击力提升", "攻擊力UP"),
    ("防御力提升", "防禦力UP"),
    ("防御力降低", "防禦力DOWN"),
    ("技能充能效率提升", "技能充能效率UP"),
    ("击退", "擊退"),
    ("灼烧", "燃燒"),
    ("冻结", "凍結"),
    ("魅惑", "魅惑"),
    ("嘲讽", "挑釁"),
    ("诺瓦露附身", "諾瓦露憑依"),
    ("永续", "永續"),
    ("累积", "累積"),
    ("发动", "發動"),
    ("普通攻击", "普通攻擊"),
    ("合计", "合計"),
]

PLACEHOLDER_RE = re.compile(r"\{\[.+?\]\}")


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        d = json.load(f)
    return d if isinstance(d, dict) else {}


def hans_to_hant(text: str, converter: opencc.OpenCC) -> str:
    zh = converter.convert(text)
    for old, new in POST_FIX:
        zh = zh.replace(old, new)
    return zh


def main() -> None:
    root = Path(__file__).parent.parent
    trans_path = root / "translations" / "ability_descriptions" / "zh_Hant.json"
    contrib_path = (
        root.parent
        / "BepInEx"
        / "plugins"
        / "AbyssMod"
        / "dump"
        / "contrib"
        / "ability_descriptions_zh_Hans.json"
    )
    auto_path = root / "reports" / "auto_ability_descriptions.json"
    gap_path = root / "reports" / "gap_ability_descriptions.json"
    report_path = root / "reports" / "import_ability_result.json"

    target = load_json(trans_path)
    hans = load_json(contrib_path)
    auto = load_json(auto_path)
    gaps = json.load(gap_path.open(encoding="utf-8")) if gap_path.exists() else []

    converter = opencc.OpenCC("s2twp")
    before = len(target)
    from_contrib = 0
    from_auto = 0
    skipped_existing = 0

    # 1. contrib（優先：人工精翻過的含佔位符句）
    for ja, hans_val in hans.items():
        if not hans_val or ja in target:
            if ja in target:
                skipped_existing += 1
            continue
        target[ja] = hans_to_hant(hans_val.strip(), converter)
        from_contrib += 1

    # 2. auto 模板譯（補無佔位符句）
    for ja, zh_val in auto.items():
        if not zh_val or ja in target:
            continue
        target[ja] = zh_val
        from_auto += 1

    with trans_path.open("w", encoding="utf-8") as f:
        json.dump(target, f, ensure_ascii=False, indent=4)

    still_missing = [g for g in gaps if g not in target]
    still_ph = [g for g in still_missing if PLACEHOLDER_RE.search(g)]

    result = {
        "before": before,
        "after": len(target),
        "from_contrib": from_contrib,
        "from_auto": from_auto,
        "still_missing": len(still_missing),
        "still_missing_with_placeholder": len(still_ph),
        "still_missing_keys": still_missing,
    }
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"zh_Hant: {before} → {len(target)}")
    print(f"  來自 contrib (Hans→Hant): {from_contrib}")
    print(f"  來自 auto_ability: {from_auto}")
    print(f"  仍缺: {len(still_missing)}（含佔位符 {len(still_ph)}）")
    print(f"  詳細清單 → {report_path}")
    if still_missing:
        print("\n仍缺樣本：")
        for g in still_missing[:10]:
            print(f"  {g[:85]!r}")


if __name__ == "__main__":
    main()
