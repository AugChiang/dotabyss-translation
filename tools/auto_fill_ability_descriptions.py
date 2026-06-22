#!/usr/bin/env python3
"""
auto_fill_ability_descriptions.py
==================================
針對 ability_descriptions 的缺口，利用：
  1. Phase 1：正規表示式複合長句模板（在個別詞替換前優先處理）
  2. Phase 2：個別術語替換
產生草稿，並合併至翻譯檔。

跳過含 {[...]} 未解析遊戲端佔位符的條目（:digit 等也含在內）。

用法
----
  python tools/auto_fill_ability_descriptions.py [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1：複合長句模板
# 需在個別詞替換前優先匹配，避免元件被提前轉換後模式失效。
# ──────────────────────────────────────────────────────────────────────────────
PHASE1_RAW: list[tuple[str, str]] = [
    # ── action skill 結構拆解 ──────────────────────────────────
    (r"【発動条件】常時発動\n【効果】(.+)",           r"【觸發條件】常時發動\n【效果】\1"),
    (r"【発動条件】通常攻撃を(\d+)回行う\n【効果】(.+)", r"【觸發條件】進行\1次普通攻擊\n【效果】\2"),
    (r"【発動条件】チェインスキル発動時\n【効果】(.+)", r"【觸發條件】連鎖技能發動時\n【效果】\1"),
    # ── 次回通常攻撃（含後綴） ─────────────────────────────────
    (r"次回の通常攻撃が(.+?)ダメージ / ノックバック【(.+?)】に変化",
     r"下次普通攻擊變為\1傷害 / 擊退【\2】"),
    (r"次回の通常攻撃が(.+?)ダメージ / (.+?)に変化",
     r"下次普通攻擊變為\1傷害 / \2"),
    (r"次回の通常攻撃が(.+?)ダメージに変化",
     r"下次普通攻擊變為\1傷害"),
    # ── 通常攻撃變化（全句） ───────────────────────────────────
    (r"通常攻撃が(.+?)ダメージ / 会心時、麻痺【(.+?)】を付与する攻撃に変化",
     r"普通攻擊變為\1傷害 / 會心時，賦予麻痺【\2】的攻擊"),
    (r"通常攻撃が(.+?)ダメージに変化", r"普通攻擊變為\1傷害"),
    # ── 状態異常解除 + 紋章付与（二合一長句） ─────────────────
    (r"味方全体の状態異常を解除 / (火・水・土|光・闇・無)属性の味方バック全体に紋章：情熱を【(\d+)】付与",
     r"解除所有友方的異常狀態 / 對\1屬性友方後排全體賦予紋章：熱情【\2】"),
    (r"味方全体の状態異常を解除 / (火・水・土|光・闇・無)属性の味方フロント全体に紋章：衝撃を【(\d+)】付与",
     r"解除所有友方的異常狀態 / 對\1屬性友方前排全體賦予紋章：衝擊【\2】"),
    (r"味方全体の状態異常を解除", "解除所有友方的異常狀態"),
    # ── 屬性目標 + 紋章付与 ────────────────────────────────────
    (r"(光・闇・無|火・水・土)属性の味方バック全体に紋章：衝撃を【(\d+)】付与",
     r"對\1屬性友方後排全體賦予紋章：衝擊【\2】"),
    (r"(光・闇・無|火・水・土)属性の味方バック全体に紋章：情熱を【(\d+)】付与",
     r"對\1屬性友方後排全體賦予紋章：熱情【\2】"),
    (r"最も攻撃力の高い(火・水・土|光・闇・無)属性の味方1体に紋章：情熱を【(\d+)】付与",
     r"對攻擊力最高的\1屬性友方1體賦予紋章：熱情【\2】"),
    (r"最も攻撃力の高い(光・闇・無|火・水・土)属性の味方1体に衝撃消費無効(\d+)回【(.+?)】を付与",
     r"對攻擊力最高的\1屬性友方1體賦予\2次無法消耗衝擊【\3】"),
    # ── 紋章：情熱達到 + バック全体 + 会心ダメージUP ──────────
    (r"紋章：情熱が(\d+)以上になったとき、(光・闇・無|火・水・土)属性の味方バック全体に会心ダメージ倍率UP【(.+?) / (.+?)】を付与",
     r"紋章：熱情達到\1時，對\2屬性友方後排全體賦予會心傷害倍率UP【\3 / \4】"),
    (r"紋章：情熱が(\d+)以上になったとき、味方バック全体に会心ダメージ倍率UP【(.+?) / (.+?)】を付与",
     r"紋章：熱情達到\1時，對友方後排全體賦予會心傷害倍率UP【\2 / \3】"),
    # ── HPが最も低い味方を中心 ────────────────────────────────
    (r"HPが最も低い味方を中心とした範囲内にいる味方全体に自身の最大HP(.+?)分の回復",
     r"以生命最低的友方為中心範圍內的所有友方回覆自身最大生命\1的生命"),
    (r"HPが最も低い味方を中心とした範囲内にいる味方全体に通常回復の(.+?)回復",
     r"以生命最低的友方為中心範圍內的所有友方回覆一般回覆的\1生命"),
    # ── チェインスキル発動時 + Buff ───────────────────────────
    (r"チェインスキル発動時、自身に攻撃力UP【(.+?) / (.+?)】を付与",
     r"連鎖技能發動時，對自身賦予攻擊力UP【\1 / \2】"),
    # ── 「が付与されたとき」被動 + 後面 Buff ──────────────────
    (r"自身に紋章：情熱が付与されたとき、自身に回避率UP【(.+?)】を付与【累積 / 最大(.+?)】",
     r"當自身的紋章：熱情被賦予時，對自身賦予迴避率UP【\1】【累積 / 最大\2】"),
    # ── 「を付与【累積」型 Buff ──────────────────────────────
    (r"回避率UP【(.+?)】を付与【累積 / 最大(.+?)】", r"賦予迴避率UP【\1】【累積 / 最大\2】"),
    # ── 連撃率が...上昇（前置 passive 效果） ──────────────────
    (r"自身の連撃率が【(.+?)】上昇", r"自身的連擊率提升【\1】"),
    (r"連撃率が【(.+?)】上昇", r"連擊率提升【\1】"),
]

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2：個別術語替換（在 Phase 1 之後執行）
# ──────────────────────────────────────────────────────────────────────────────
PHASE2_RAW: list[tuple[str, str]] = [
    # 結構詞
    ("【発動条件】", "【觸發條件】"),
    ("【効果】", "【效果】"),
    # 時間/頻率
    (r"(\d+)秒に1回", r"每\1秒1次"),
    # 目標片語（長匹配優先）
    (r"HPが最も低い(火・水・土|光・闇・無)属性の味方フロント・バックの1体", r"生命最低的\1屬性友方前排・後排1體"),
    (r"HP割合が最も低い味方1体", "HP比例最低的1個友方"),
    (r"HPが最も低い味方1体", "生命最低的1個友方"),
    (r"HPが最も高い敵1体", "生命最高的1個敵人"),
    (r"最も攻撃力の高い(火・水・土|光・闇・無)属性の味方1体", r"攻擊力最高的\1屬性友方1體"),
    (r"攻撃力が最も高い(火・水・土|光・闇・無)属性の味方1体", r"攻擊力最高的\1屬性友方1體"),
    (r"(火・水・土|光・闇・無)属性の味方バック全体", r"\1屬性友方後排全體"),
    (r"(火・水・土|光・闇・無)属性の味方フロント全体", r"\1屬性友方前排全體"),
    (r"(火・水・土|光・闇・無)属性の味方1体", r"\1屬性友方1體"),
    (r"火・水・土", "火・水・土"),
    (r"光・闇・無", "光・暗・無"),
    (r"火属性の", "火屬性的"),
    (r"水属性の", "水屬性的"),
    (r"土属性の", "土屬性的"),
    (r"光属性の", "光屬性的"),
    (r"闇属性の", "暗屬性的"),
    (r"無属性の", "無屬性的"),
    (r"味方バック全体", "友方後排全體"),
    (r"味方フロント全体", "友方前排全體"),
    (r"フロント・バックの1体", "前排・後排的1體"),
    (r"味方全体", "所有友方"),
    (r"敵全体", "所有敵人"),
    (r"味方(\d+)体", r"\1個友方"),
    (r"味方1体", "1個友方"),
    (r"敵1体", "1個敵人"),
    (r"自身の最大HP", "自身最大生命"),
    (r"自身に", "對自身"),
    (r"自身の", "自身的"),
    (r"自身", "自身"),
    (r"対象に", "對目標"),
    (r"対象", "目標"),
    # さらに
    (r"さらに", "另外"),
    # 紋章句式
    (r"紋章：情熱を【(\d+)】付与", r"賦予紋章：熱情【\1】"),
    (r"紋章：衝撃を【(\d+)】付与", r"賦予紋章：衝擊【\1】"),
    (r"紋章：情熱が(\d+)以上になったとき、", r"紋章：熱情達到\1時，"),
    (r"紋章：情熱が(\d+)以上のとき、", r"紋章：熱情達到\1時，"),
    (r"紋章：衝撃を(\d+)消費し、", r"消耗\1紋章：衝擊，"),
    (r"紋章：衝撃を(\d+)消費し", r"消耗\1紋章：衝擊"),
    (r"紋章：情熱", "紋章：熱情"),
    (r"紋章：衝撃", "紋章：衝擊"),
    # 回復句式
    (r"最大HP(.+?)分の回復", r"最大生命\1的回覆"),
    (r"通常回復の(.+?)回復", r"一般回覆的\1回覆"),
    (r"状態異常を解除", "解除異常狀態"),
    # Buff 付与句式
    (r"攻撃力UP【(.+?) / (.+?)】を付与", r"賦予攻擊力UP【\1 / \2】"),
    (r"防御力UP【(.+?) / (.+?)】を付与", r"賦予防禦力UP【\1 / \2】"),
    (r"会心率UP【(.+?) / (.+?)】を付与", r"賦予會心率UP【\1 / \2】"),
    (r"会心ダメージ倍率UP【(.+?) / (.+?)】を付与", r"賦予會心傷害倍率UP【\1 / \2】"),
    (r"スキルダメージUP【(.+?) / (.+?)】を付与", r"賦予技能傷害UP【\1 / \2】"),
    (r"最大HPのバリア【(.+?)】を付与", r"賦予最大生命護盾【\1】"),
    (r"バリア【(.+?)】を付与", r"賦予護盾【\1】"),
    (r"麻痺【(.+?)】を付与", r"賦予麻痺【\1】"),
    (r"炎上【(.+?)】を付与", r"賦予燃燒【\1】"),
    (r"凍結が【(.+?) / (.+?)】に変化", r"凍結變為【\1 / \2】"),
    (r"凍結【(.+?)】を付与", r"賦予凍結【\1】"),
    (r"石化【(.+?)】を付与", r"賦予石化【\1】"),
    (r"喪失【(.+?)】を付与", r"賦予喪失【\1】"),
    (r"挑発【(.+?)】を付与", r"賦予挑釁【\1】"),
    (r"衝撃消費無効(\d+)回【(.+?)】を付与", r"賦予\1次無法消耗衝擊【\2】"),
    (r"ノックバック【(.+?)】", r"擊退【\1】"),
    # マナ
    (r"マナを【(.+?)】チャージ", r"充能【\1】點能量"),
    # 剩餘 に 後接中文動詞（對象格後補）
    (r"(友方(?:後排|前排)?全體|友方[\d體後前排]+|所有友方|所有敵人|目標|自身)に(賦予|解除|回覆)",
     r"對\1\2"),
    # 其他常用詞
    (r"会心時、", "會心時，"),
    (r"会心時", "會心時"),
    (r"クエスト中(\d+)回まで", r"每次任務限\1次"),
    (r"永続", "永久"),
    (r"ダメージ", "傷害"),
    (r"回復", "回覆"),
    (r"付与", "賦予"),
    (r"変化", "變化"),
    (r"成功率：", "成功率："),
    (r"成功率:", "成功率:"),
    # 追加詞彙
    (r"魅了【(.+?)】", r"魅惑【\1】"),
    (r"回避率UP【(.+?)】を付与", r"賦予迴避率UP【\1】"),
    (r"回避率UP【(.+?)】", r"迴避率UP【\1】"),
    # 被動形：「が付与されたとき」→「被賦予時」
    (r"が付与されたとき、", "被賦予時，"),
    (r"が付与されたとき", "被賦予時"),
    # 累積記法
    (r"【累積 / 最大(.+?)】", r"【累積 / 最大\1】"),
    (r"を付与【累積", "賦予【累積"),
]

# 未解析佔位符正則
# 格式有兩種：{[PREFIX.FIELD]} 或 {[PREFIX.FIELD]秒} (方括號後接內容再接花括號)
UNRESOLVED_RE = re.compile(
    r"\{\[(?:PRJCTL|AOE|RECOVER|DAMAGE|ABNORMAL|MANA|ATTACK|IMPACT|BARRIER|CRITICALUP|IMPACTSUCCEED|LAND|THROW|ATTACKUP|SUMMON|SKILLDAMAGE|ZEAL|SUMMON_MIRROR|SUMMON_SERVANT|DRAIN)[\.\w:]*\][^}]*\}"
)

# 剩餘假名偵測（排除 ・ U+30FB 中黑點，中文也用）
RESIDUAL_KANA_RE = re.compile(r"[\u3040-\u30fa\u30fc-\u30ff]")

# 編譯
_P1: list[tuple[re.Pattern, str]] = [(re.compile(p), r) for p, r in PHASE1_RAW]
_P2: list[tuple[re.Pattern, str]] = [(re.compile(p), r) for p, r in PHASE2_RAW]


def has_unresolved(text: str) -> bool:
    return bool(UNRESOLVED_RE.search(text))


def apply_phase(text: str, patterns: list[tuple[re.Pattern, str]]) -> str:
    result = text
    for pat, repl in patterns:
        result = pat.sub(repl, result)
    return result


def translate(ja: str) -> str:
    after_p1 = apply_phase(ja, _P1)
    after_p2 = apply_phase(after_p1, _P2)
    return after_p2


def is_clean(zh: str) -> bool:
    return not RESIDUAL_KANA_RE.search(zh)


def build_draft(gaps: list[str]) -> dict[str, str]:
    draft: dict[str, str] = {}
    skipped = 0
    auto_ok = 0
    auto_partial = 0
    partial_samples: list[tuple[str, str]] = []

    for ja in gaps:
        if has_unresolved(ja):
            skipped += 1
            continue

        zh = translate(ja)
        if is_clean(zh):
            draft[ja] = zh
            auto_ok += 1
        else:
            draft[ja] = ""
            auto_partial += 1
            if len(partial_samples) < 5:
                partial_samples.append((ja, zh))

    print(f"  跳過未解析佔位符: {skipped}")
    print(f"  自動翻譯完成: {auto_ok}")
    print(f"  需人工校對: {auto_partial}")
    if partial_samples:
        print("  殘留假名樣本：")
        for ja, zh in partial_samples:
            residual = set(RESIDUAL_KANA_RE.findall(zh))
            print(f"    JA: {ja[:70]!r}")
            print(f"    ZH: {zh[:70]!r}")
            print(f"    殘留: {residual}")
    return draft


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只輸出草稿，不寫入翻譯檔")
    parser.add_argument(
        "--gap-file",
        default=str(Path(__file__).parent.parent / "reports" / "gap_ability_descriptions.json"),
    )
    parser.add_argument(
        "--translations-file",
        default=str(
            Path(__file__).parent.parent
            / "translations"
            / "ability_descriptions"
            / "zh_Hant.json"
        ),
    )
    parser.add_argument(
        "--output-file",
        default=str(
            Path(__file__).parent.parent / "reports" / "auto_ability_descriptions.json"
        ),
    )
    args = parser.parse_args()

    gap_path = Path(args.gap_file)
    trans_path = Path(args.translations_file)
    out_path = Path(args.output_file)

    print("=== Step 1: 讀取缺口清單 ===")
    with gap_path.open(encoding="utf-8") as f:
        gaps: list[str] = json.load(f)
    print(f"  缺口數: {len(gaps)}")

    print("\n=== Step 2: 兩階段模板翻譯 ===")
    draft = build_draft(gaps)

    print("\n=== Step 3: 寫出草稿 ===")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    print(f"  草稿 → {out_path}")

    good = {k: v for k, v in draft.items() if v}
    print(f"\n  可合並條目 (value 非空): {len(good)}")

    if args.dry_run:
        print("  --dry-run 模式，跳過寫入翻譯檔。")
        return

    print("\n=== Step 4: 合並至翻譯檔（僅新增，不覆蓋） ===")
    with trans_path.open(encoding="utf-8-sig") as f:
        existing = json.load(f)
    before = len(existing)
    merged = 0
    for k, v in good.items():
        if k not in existing:
            existing[k] = v
            merged += 1
    with trans_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=4)
    print(f"  新增 {merged} 條 (原有 {before} → 現在 {len(existing)})")


if __name__ == "__main__":
    main()
