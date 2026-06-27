import json
import subprocess
from pathlib import Path
from typing import Dict, Tuple, List
import os

os.environ["PYTHONUTF8"] = "1"

# -----------------------------
# CONFIG
# -----------------------------
SOURCE_BRANCH = "main"
TARGET_BRANCH = "story-only"
FOLDERS = ["translations\\descriptions", "translations\\manifest", "translations\\novels"] # list of folders to sync

REMOVE_DELETED_KEYS = False  # set True if you want pruning

# -----------------------------
# GIT HELPERS
# -----------------------------
def git_show(branch: str, path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "show", f"{branch}:{path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8-sig",   # handles BOM correctly
            errors="replace",
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def list_json_files(branch: str, folder: str):
    """
    Only return .json files from a given branch + folder.
    """
    try:
        files = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", branch, folder],
            text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        return []

    return [f for f in files if f.endswith(".json")]

def get_changed_json_files():
    result = subprocess.check_output(
        ["git", "diff", "--name-only", f"{SOURCE_BRANCH}..{TARGET_BRANCH}"],
        text=True
    )

    files = result.splitlines()

    filtered = []
    for f in files:
        if not f.endswith(".json"):
            continue
        if not any(f.startswith(folder + "/") for folder in FOLDERS):
            continue
        filtered.append(f)

    return filtered


# -----------------------------
# JSON LOAD / SAVE
# -----------------------------
def load_json_from_git(branch: str, path: str) -> Dict:
    content = git_show(branch, path)
    if content is None:
        return {}
    return json.loads(content)


def dump_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -----------------------------
# MERGE LOGIC
# -----------------------------
def merge_translation(source: Dict[str, str], target: Dict[str, str]) -> Tuple[Dict, Dict]:
    report = {
        "added": [],
        "removed": [],
        "kept": [],
    }

    merged = {}

    # Add / keep
    for k, v in source.items():
        if k in target:
            merged[k] = target[k]
            report["kept"].append(k)
        else:
            merged[k] = ""
            report["added"].append(k)

    # Handle deletions
    if not REMOVE_DELETED_KEYS:
        for k in target.keys():
            if k not in merged:
                merged[k] = target[k]
                report["removed"].append(k)

    return merged, report


# -----------------------------
# REPORT
# -----------------------------
def print_report(file_path: str, report: Dict):
    print(f"\n=== {file_path} ===")

    if report["added"]:
        print("\n[ADDED]")
        for k in report["added"]:
            print(f"  + {k}")

    if report["removed"]:
        print("\n[REMOVED]")
        for k in report["removed"]:
            print(f"  - {k}")

    if report["kept"]:
        print("\n[KEPT]")
        for k in report["kept"]:
            print(f"  ✓ {k}")


# -----------------------------
# MAIN SYNC
# -----------------------------
# def sync():
      # get all files
#     for folder in FOLDERS:
#         json_files = list_json_files(SOURCE_BRANCH, folder)
#         for file_path in json_files:
#             print(f"\nProcessing: {file_path}")
#             # HARD GUARD (extra safety)
#             if not file_path.endswith(".json"):
#                 continue

#             source_json = load_json_from_git(SOURCE_BRANCH, file_path)
#             target_json = load_json_from_git(TARGET_BRANCH, file_path)

#             merged, report = merge_translation(source_json, target_json)

#             out_path = Path(file_path)
#             dump_json(out_path, merged)

#             print_report(file_path, report)

def sync():
    json_files = get_changed_json_files()

    print(f"Found {len(json_files)} changed JSON files")

    for file_path in json_files:
        print(f"\nProcessing: {file_path}")

        source_json = load_json_from_git(SOURCE_BRANCH, file_path)
        target_json = load_json_from_git(TARGET_BRANCH, file_path)

        merged, report = merge_translation(source_json, target_json)

        dump_json(Path(file_path), merged)
        print_report(file_path, report)

# -----------------------------
# OPTIONAL COMMIT
# -----------------------------
def commit_changes():
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", "Sync JSON translations"])
    subprocess.run(["git", "push", "origin", TARGET_BRANCH])


if __name__ == "__main__":
    sync()
    # commit_changes()