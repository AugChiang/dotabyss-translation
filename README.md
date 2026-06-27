# dotabyss-translation

ドットアビス（Dot Abyss）AbyssMod 中文翻譯資料 CDN。

配合 [s88037zz/AbyssMod](https://github.com/s88037zz/AbyssMod) **v1.1.0+** 使用。插件啟動時會從此 repo 下載 JSON 到本機 `BepInEx/plugins/AbyssMod/cache/translations/`。

## 使用者設定

編輯 `BepInEx/config/AbyssMod.cfg`：

```ini
[Translation]
CDN = https://raw.githubusercontent.com/s88037zz/dotabyss-translation/main/translations
Language = zh_Hant
Enabled = true
```

若 GitHub 連線不穩，可改用鏡像：

```ini
CDN = https://gh-proxy.com/https://raw.githubusercontent.com/s88037zz/dotabyss-translation/main/translations
```

**升級至 AbyssMod 1.1.0 後**，建議刪除舊 cache：`BepInEx/plugins/AbyssMod/cache/translations/`，讓插件重新下載新結構。

## 目錄說明（作者 m_* 扁平結構）

| 路徑 | 內容 |
|------|------|
| `manifest/zh_Hant.json` | 各檔案版本雜湊（含 `m_*`、`names`、`ui_texts`、`novels`、`add_on.ui_misc`） |
| `names/zh_Hant.json` | 角色名 |
| `ui_texts/zh_Hant.json` | 短 UI 標籤（底部導航、設定等） |
| `m_tavern_character_cards/zh_Hant.json` | 酒館營業卡（masterdata 原文 key） |
| `m_ability_details/zh_Hant.json` | 技能 / 覺醒描述 |
| `m_missions/zh_Hant.json` | 任務標題 |
| `m_nether_floor_event_parts/zh_Hant.json` | 深淵 floor 事件選項 |
| `m_*/zh_Hant.json` | 其餘 masterdata 字典（見 `AbyssMod.master_mapping.json`） |
| `novels/{id}/zh_Hant.json` | 劇情對話 |
| `legacy/add-on/ui_misc/zh_Hant.json` | UI 兜底字典（`manifest.add_on.ui_misc`） |
| `other/{category}/` | 機翻後人工校對補充（可選） |

CDN 下載範例：`{CDN}/m_tavern_character_cards/zh_Hant.json`

## 維護工具

```bash
# 從舊 add-on 結構遷移至 m_*（需 Lienchu 參考包）
python tools/migrate_to_author_layout.py

# 重建 manifest 雜湊
python tools/rebuild_manifest.py

# Masterdata 缺口報告（對齊 m_* 路徑）
python tools/masterdata_gap_report.py
```

## 貢獻

歡迎 PR 修正譯文。`m_*` 表請使用 masterdata 日文原文作 key（勿提交含 `<color>` / `{0}` 的 runtime 模板 key 至酒館卡等表）。

## 致謝

劇情翻譯框架與 masterdata 映射源自 [anosu/AbyssMod](https://github.com/anosu/AbyssMod)；`m_missions` / floor events 等參考 Lienchu 社群包。
