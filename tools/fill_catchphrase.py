# -*- coding: utf-8 -*-
"""建立 add-on/catchphrase/zh_Hant.json：翻譯角色標語（過濾佔位字串）。"""
import json, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "translations/add-on/catchphrase/zh_Hant.json")
PLACEHOLDER = re.compile(r"^キャッチフレーズ\d*$")

url = "https://raw.githubusercontent.com/DotAbyss/Masterdata/main/data/m_character_profiles.json"
rows = json.loads(urllib.request.urlopen(url, timeout=30).read())

phrases = []
for r in rows:
    c = r.get("catchphrase")
    if isinstance(c, str) and c.strip() and not PLACEHOLDER.match(c.strip()):
        phrases.append(c)

ZH = [
    "可別把視線移開喔\n好好沉醉在我的舞蹈裡吧♪",
    "鎖定的目標絕不放過\n畢竟我也只會這點本事……",
    "呼呼呼！　果然我是天才！\n最棒的發明品就快完成了……",
    "上吧，諾瓦爾！\n讓大家見識我們的力量吧！",
    "我所信賴的，只有火焰\n與這支箭。來吧，將一切燃燒殆盡",
    "主人的指示是絕對的。艾蕾克特拉\n會回應任何命令",
    "只要和姊姊在一起，\n無論在什麼地方、面對什麼對手，我都不會輸。",
    "你想要狩獵的夥伴對吧？　\n我就陪你一程吧",
    "嗨大家好～我是皮可喵！\n現在正來到異世界囉～",
    "星空就是航海圖！　風是朋友！\n再大的暴風雨我都會跨越給你看！",
    "打頭陣是我的職責！\n各位，跟著我上吧！",
    "嘿咻～！\n水之精靈之力大爆發！",
    "瑪妞才不寂寞呢……\n因為有小麥在嘛",
    "魔法的力量是無限大的！",
    "就讓你瞧瞧美麗的冰雕吧。\n雖然你或許無法理解就是了。",
    "我會用艾蜜莉的笑容讓客人感到幸福哦！",
    "本店最有人氣的莓果塔，\n請享用！",
    "都說我不是小孩子了！\n你想成為我刀下的亡魂嗎？",
    "俐落、不浪費，\n就是我的座右銘。",
    "呼呼呼，今天的占卜完美無缺！　\n出現了好結果哦！",
    "沒見過的素材、不曾接觸的技術……\n咕～嗚～，真是令人興奮到極點啊！",
    "小鳥們總是自由自在地\n飛翔，看起來好開心呢♪",
    "目標是一夜致富！\n寶藏到底在哪裡呢～？",
]

assert len(phrases) == len(ZH), f"數量不符 jp={len(phrases)} zh={len(ZH)}\n" + "\n".join(repr(p) for p in phrases)

data = dict(zip(phrases, ZH))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"已寫入 {len(data)} 條標語 -> {OUT}")
