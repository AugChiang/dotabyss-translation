# -*- coding: utf-8 -*-
"""Pass2 批次補齊：names / abyss_code / descriptions。
- names: 補 ルシータ
- abyss_code: 刪除「中文 key」死條目 + 補 9 條缺口
- descriptions: 服裝公式化清譯 + 既有 MT(s2twp) 清理後合併
"""
import json, re, os
import opencc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cc = opencc.OpenCC("s2twp")
KANA = re.compile(r"[\u3041-\u309f\u30a1-\u30fa\u30fc]")
HAN = re.compile(r"[\u4e00-\u9fff]")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")


P_NAMES = os.path.join(ROOT, "translations/names/zh_Hant.json")
P_ABYSS = os.path.join(ROOT, "translations/add-on/abyss_code/zh_Hant.json")
P_DESC = os.path.join(ROOT, "translations/descriptions/zh_Hant.json")
P_GAP_DESC = os.path.join(ROOT, "reports/gap_descriptions.json")
P_MT_DESC = os.path.join(ROOT, "reports/mt_progress_descriptions.json")

report = {}

# ---------- 1. names ----------
names = load(P_NAMES)
NAME_ADD = {"ルシータ": "露西塔"}
n_added = 0
for k, v in NAME_ADD.items():
    if k not in names:
        names[k] = v
        n_added += 1
save(P_NAMES, names)
report["names_added"] = n_added

# ---------- 2. abyss_code ----------
abyss = load(P_ABYSS)
# 刪除中文 key 死條目（含漢字、無真假名）
dead = [k for k in abyss if HAN.search(k) and not KANA.search(k)]
for k in dead:
    del abyss[k]
report["abyss_dead_removed"] = len(dead)

ABYSS_ADD = {
    "バックキャラに紋章：情熱が付与された時、15秒間付与されたキャラのスキルダメージが【10%】上昇する":
        "後排角色被附加紋章：熱情時，15秒內被附加的角色技能傷害提升【10%】",
    "バックキャラに紋章：情熱が付与された時、15秒間付与されたキャラの連撃率が【10%】上昇する":
        "後排角色被附加紋章：熱情時，15秒內被附加的角色連擊率提升【10%】",
    "バックキャラに紋章：衝撃が付与された時、15秒間付与されたキャラの連撃率が【10%】上昇する":
        "後排角色被附加紋章：衝擊時，15秒內被附加的角色連擊率提升【10%】",
    "バックキャラの紋章：衝撃が消費された時、15秒間バック全体の連撃率が【20%】上昇する":
        "後排角色的紋章：衝擊被消耗時，15秒內後排全體連擊率提升【20%】",
    "フロントキャラがFC発動時、15秒間フロント全体の会心ダメージが【50%】上昇する":
        "前排角色發動FC時，15秒內前排全體爆擊傷害提升【50%】",
    "フロントキャラに紋章：衝撃が付与された時、15秒間付与されたキャラの連撃率が【10%】上昇する":
        "前排角色被附加紋章：衝擊時，15秒內被附加的角色連擊率提升【10%】",
    "フロントキャラの紋章：衝撃が消費された時、15秒間フロント全体のスキルダメージが【50%】上昇する":
        "前排角色的紋章：衝擊被消耗時，15秒內前排全體技能傷害提升【50%】",
    "戦闘開始時、最大HPが【10%】上昇する": "戰鬥開始時，最大HP提升【10%】",
    "戦闘開始時、最大HPが【20%】上昇する": "戰鬥開始時，最大HP提升【20%】",
}
a_added = 0
for k, v in ABYSS_ADD.items():
    if k not in abyss:
        abyss[k] = v
        a_added += 1
save(P_ABYSS, abyss)
report["abyss_added"] = a_added

# ---------- 3. descriptions ----------
desc = load(P_DESC)
gap = set(load(P_GAP_DESC))
mt = load(P_MT_DESC)

# 3a. 服裝公式化：「○○の基本コスチュームです。」-> 「{中文名}的基本服裝。」
COST_RE = re.compile(r"^(.+?)の基本コスチュームです。$")
cost_missing = []
cost_added = 0
for k in gap:
    m = COST_RE.match(k)
    if not m:
        continue
    jp_name = m.group(1)
    zh = names.get(jp_name)
    if zh is None:
        cost_missing.append(jp_name)
        continue
    desc[k] = f"{zh}的基本服裝。"
    cost_added += 1
report["costume_added"] = cost_added
report["costume_missing_name"] = cost_missing

# 3b. 其餘走 MT(s2twp)，清理後仍含假名者跳過（品質不足，留待人工）
mt_added = 0
mt_skipped_kana = 0
mt_no_value = 0
for k in gap:
    if k in desc:  # 已被服裝步驟或既有翻譯填上
        continue
    raw = mt.get(k, "")
    if not raw:
        mt_no_value += 1
        continue
    conv = cc.convert(raw)
    if KANA.search(conv):
        mt_skipped_kana += 1
        continue
    desc[k] = conv
    mt_added += 1
save(P_DESC, desc)
report["mt_added"] = mt_added
report["mt_skipped_kana"] = mt_skipped_kana
report["mt_no_value"] = mt_no_value

print(json.dumps(report, ensure_ascii=False, indent=2))
