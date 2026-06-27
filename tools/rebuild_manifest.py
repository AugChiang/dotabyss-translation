#!/usr/bin/env python3
"""
rebuild_manifest.py
====================
重建 translations/manifest/zh_Hant.json 中各翻譯檔的 MD5 雜湊值。

支援作者扁平 m_* 結構 + legacy/add_on 兜底 + novels 子目錄。

用法
----
  python tools/rebuild_manifest.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MAPPING_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "AbyssMod-main"
    / "AbyssMod"
    / "AbyssMod.master_mapping.json"
)


def get_hash(d: dict[str, str]) -> str:
    parts = []
    for k in sorted(d.keys()):
        parts.extend([k, "\0", d[k], "\0"])
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def load_dict_types() -> list[str]:
    if not MAPPING_JSON.exists():
        return []
    with MAPPING_JSON.open(encoding="utf-8") as f:
        return list(json.load(f).get("dict_types", []))


def main() -> None:
    base = Path(__file__).parent.parent / "translations"
    manifest_path = base / "manifest" / "zh_Hant.json"
    manifest = load_json(manifest_path)
    print(f"現有 manifest keys: {list(manifest.keys())}")

    # 作者扁平 dict_types（names, ui_texts, m_*）
    for key in load_dict_types():
        path = base / key / "zh_Hant.json"
        d = load_json(path)
        if not d:
            manifest.pop(key, None)
            print(f"  {key}: 跳過（空或不存在）")
            continue
        new_hash = get_hash(d)
        old_hash = manifest.get(key, "")
        if old_hash != new_hash:
            print(f"  {key}: {old_hash!r} → {new_hash!r}")
        else:
            print(f"  {key}: 不變")
        manifest[key] = new_hash

    # 過渡期 legacy 頂層（若仍存在）
    for key in ("titles", "descriptions", "another_name", "ability_descriptions"):
        path = base / key / "zh_Hant.json"
        d = load_json(path)
        if d:
            manifest[key] = get_hash(d)
            print(f"  {key} (legacy): {manifest[key]!r}")
        else:
            manifest.pop(key, None)

    # novels/
    novels_dir = base / "novels"
    if novels_dir.exists():
        novel_hashes: dict[str, str] = manifest.get("novels", {})
        for novel_dir in sorted(novels_dir.iterdir()):
            if not novel_dir.is_dir():
                continue
            lang_file = novel_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if not d:
                continue
            nid = novel_dir.name
            novel_hashes[nid] = get_hash(d)
        manifest["novels"] = novel_hashes
        print(f"  novels: {len(novel_hashes)} 本")

    # legacy/add-on/ui_misc → manifest.add_on.ui_misc
    legacy_ui_misc = base / "legacy" / "add-on" / "ui_misc" / "zh_Hant.json"
    fallback_ui_misc = base / "add-on" / "ui_misc" / "zh_Hant.json"
    ui_misc_path = legacy_ui_misc if legacy_ui_misc.exists() else fallback_ui_misc
    add_on_hashes: dict[str, str] = manifest.get("add_on", {})
    if ui_misc_path.exists():
        d = load_json(ui_misc_path)
        if d:
            add_on_hashes["ui_misc"] = get_hash(d)
            print(f"  add_on.ui_misc: {add_on_hashes['ui_misc']!r}")
    manifest["add_on"] = add_on_hashes or manifest.get("add_on")

    # other/ 子類別（機翻社群）
    other_dir = base / "other"
    if other_dir.exists():
        other_hashes: dict[str, str] = manifest.get("other", {})
        for cat_dir in sorted(other_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            lang_file = cat_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if d:
                other_hashes[cat_dir.name] = get_hash(d)
        if other_hashes:
            manifest["other"] = other_hashes

    # 頂層 meta hash
    top_for_meta = {
        k: v
        for k, v in manifest.items()
        if k != "hash" and isinstance(v, str)
    }
    manifest["hash"] = get_hash(top_for_meta)
    print(f"\n  manifest.hash → {manifest['hash']!r}")

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4, sort_keys=True)
        f.write("\n")
    print(f"\n manifest 已寫入 {manifest_path}")


if __name__ == "__main__":
    main()
