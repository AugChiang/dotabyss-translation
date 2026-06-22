#!/usr/bin/env python3
"""
rebuild_manifest.py
====================
重建 translations/manifest/zh_Hant.json 中各翻譯檔的 MD5 雜湊值。

演算法（與 AbyssMod TranslationCache.GetHash 一致）：
  1. 讀取 JSON 字典
  2. 對所有 key 按 Ordinal 排序
  3. 依 key\0value\0 格式拼接成字串
  4. MD5 UTF-8 bytes → hex 小寫

用法
----
  python tools/rebuild_manifest.py
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def get_hash(d: dict[str, str]) -> str:
    """與 C# TranslationCache.GetHash 相同演算法。"""
    parts = []
    for k in sorted(d.keys()):
        parts.append(k)
        parts.append("\0")
        parts.append(d[k])
        parts.append("\0")
    raw = "".join(parts).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def main() -> None:
    base = Path(__file__).parent.parent / "translations"
    manifest_path = base / "manifest" / "zh_Hant.json"

    # 讀取現有 manifest
    manifest = load_json(manifest_path)
    print(f"現有 manifest keys: {list(manifest.keys())}")

    # 重建 top-level 翻譯檔雜湊
    top_level_map = {
        "names":        base / "names" / "zh_Hant.json",
        "titles":       base / "titles" / "zh_Hant.json",
        "descriptions": base / "descriptions" / "zh_Hant.json",
        "another_name": base / "another_name" / "zh_Hant.json",
        "ability_descriptions": base / "ability_descriptions" / "zh_Hant.json",
    }
    for key, path in top_level_map.items():
        d = load_json(path)
        if d:
            new_hash = get_hash(d)
            old_hash = manifest.get(key, "")
            if old_hash != new_hash:
                print(f"  {key}: {old_hash!r} → {new_hash!r}")
            else:
                print(f"  {key}: 不變")
            manifest[key] = new_hash

    # 重建 other/ 子類別雜湊
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
            if not d:
                continue
            cat = cat_dir.name
            new_hash = get_hash(d)
            old_hash = other_hashes.get(cat, "")
            if old_hash != new_hash:
                print(f"  other/{cat}: {old_hash!r} → {new_hash!r}")
            else:
                print(f"  other/{cat}: 不變")
            other_hashes[cat] = new_hash
        manifest["other"] = other_hashes

    # 重建 add-on/ 子類別雜湊
    add_on_dir = base / "add-on"
    if add_on_dir.exists():
        add_on_hashes: dict[str, str] = manifest.get("add_on", {})
        for cat_dir in sorted(add_on_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            lang_file = cat_dir / "zh_Hant.json"
            if not lang_file.exists():
                continue
            d = load_json(lang_file)
            if not d:
                continue
            cat = cat_dir.name
            new_hash = get_hash(d)
            old_hash = add_on_hashes.get(cat, "")
            if old_hash != new_hash:
                print(f"  add-on/{cat}: {old_hash!r} → {new_hash!r}")
            else:
                print(f"  add-on/{cat}: 不變")
            add_on_hashes[cat] = new_hash
        manifest["add_on"] = add_on_hashes

    # 重建頂層整體 hash（hash of all top-level hashes）
    # 注意：manifest["hash"] 是對整個 manifest 的 digest，使用相同算法
    # key = manifest key, value = hash string
    top_for_meta = {k: v for k, v in manifest.items() if k != "hash" and isinstance(v, str)}
    manifest["hash"] = get_hash(top_for_meta)
    print(f"\n  manifest.hash → {manifest['hash']!r}")

    # 寫回
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4, sort_keys=True)
    print(f"\n manifest 已寫入 {manifest_path}")


if __name__ == "__main__":
    main()
