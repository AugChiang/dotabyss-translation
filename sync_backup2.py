import json
import subprocess
from pathlib import Path
from typing import Dict, Tuple, List

# -----------------------------
# CONFIG
# -----------------------------
SOURCE_BRANCH = "main"
TARGET_BRANCH = "story-only"
FOLDERS = ["translations/novels/evs_10200010101"]

STATE_FILE = ".sync_state.json"

REMOVE_DELETED_KEYS = False

# -----------------------------
# GIT HELPERS
# -----------------------------
def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def get_commit(branch: str) -> str:
    return run(["git", "rev-parse", branch])


def git_show(branch: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{branch}:{path}"],
            text=True,
            encoding="utf-8-sig",
            errors="replace"
        )
    except subprocess.CalledProcessError:
        return None


# -----------------------------
# STATE HANDLING
# -----------------------------
def load_state() -> Dict:
    if not Path(STATE_FILE).exists():
        return None

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def init_state_if_missing():
    """
    Create initial state if missing.
    """
    if Path(STATE_FILE).exists():
        return load_state()

    state = {
        "main": get_commit(SOURCE_BRANCH),
        "story-only": get_commit(TARGET_BRANCH)
    }

    save_state(state)
    print("Initialized .sync_state.json")
    return state


# -----------------------------
# FILE DIFF
# -----------------------------
def get_changed_json_files(old_main: str, new_main: str) -> List[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", old_main, new_main],
        text=True
    )

    files = output.splitlines()

    result = []
    for f in files:
        if not f.endswith(".json"):
            continue
        if not any(f.startswith(folder + "/") for folder in FOLDERS):
            continue
        result.append(f)

    return result


# -----------------------------
# JSON IO
# -----------------------------
def load_json_from_git(branch: str, path: str) -> Dict:
    content = git_show(branch, path)
    if not content:
        return {}
    return json.loads(content)


def dump_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -----------------------------
# MERGE LOGIC
# -----------------------------
def merge_translation(source: Dict, target: Dict) -> Tuple[Dict, Dict]:
    report = {"added": [], "removed": [], "kept": []}
    merged = {}

    for k in source:
        if k in target:
            merged[k] = target[k]
            report["kept"].append(k)
        else:
            merged[k] = ""
            report["added"].append(k)

    if not REMOVE_DELETED_KEYS:
        for k in target:
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
def sync():
    # Step 1: ensure state exists
    state = init_state_if_missing()

    old_main = state["main"]

    # Step 2: get latest commits
    new_main = get_commit(SOURCE_BRANCH)
    new_story_only = get_commit(TARGET_BRANCH)

    # 🔥 IMPORTANT: update story-only FIRST (as requested)
    state["story-only"] = new_story_only
    save_state(state)

    # Step 3: compute changed files since last sync
    changed_files = get_changed_json_files(old_main, new_main)

    print(f"Changed JSON files: {len(changed_files)}")

    if not changed_files:
        print("No changes detected.")
        state["main"] = new_main
        save_state(state)
        return

    # Step 4: process files
    for file_path in changed_files:
        print(f"\nProcessing: {file_path}")

        source_json = load_json_from_git(SOURCE_BRANCH, file_path)
        target_json = load_json_from_git(TARGET_BRANCH, file_path)

        merged, report = merge_translation(source_json, target_json)

        dump_json(Path(file_path), merged)
        print_report(file_path, report)

    # Step 5: update main commit AFTER sync
    state["main"] = new_main
    save_state(state)

    print("\nSync complete.")


# -----------------------------
# OPTIONAL COMMIT
# -----------------------------
def commit_changes():
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", "Sync translations"])
    subprocess.run(["git", "push", "origin", TARGET_BRANCH])


if __name__ == "__main__":
    sync()
    # commit_changes()