#!/usr/bin/env python3
"""从 migrate_to_author_layout 调用：产出 legacy 重复 key 列表（不修改文件）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 允许作为模块导入 duplicate_key_report
sys.path.insert(0, str(Path(__file__).resolve().parent))
from duplicate_key_report import (  # noqa: E402
    collect_sources,
    keys_to_remove_from_legacy,
)


def export_legacy_keys_to_remove(translations_dir: Path, reports_dir: Path) -> Path:
    sources = collect_sources(translations_dir)
    remove_map = keys_to_remove_from_legacy(sources)
    remove_map = {k: v for k, v in remove_map.items() if v}
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "legacy_keys_to_remove.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(remove_map, f, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    p = export_legacy_keys_to_remove(root / "translations", root / "reports")
    print(f"Wrote {p}")
