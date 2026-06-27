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
# STATE
# -----------------------------
def load_state():
    if not Path(STATE_FILE).exists():
        return None
    return json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))


def save_state(state):
    Path(STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def init_state_if_missing():
    if Path(STATE_FILE).exists():
        return load_state()

    state = {
        "main": get_commit(SOURCE_BRANCH),
        "dist": get_commit(TARGET_BRANCH)
    }
    save_state(state)
    print("Initialized sync state.")
    return state


# -----------------------------
# FILE DIFF DETECTION
# -----------------------------
def get_changed_files(old: str, new: str) -> Set[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", old, new],
        text=True
    )

    result = set()
    for f in output.splitlines():
        if not f.endswith(".json"):
            continue
        if not any(f.startswith(folder + "/") for folder in FOLDERS):
            continue
        result.add(f)

    return result


def detect_changes(state):
    old_main = state["main"]
    old_dist = state["dist"]

    new_main = get_commit(SOURCE_BRANCH)
    new_dist = get_commit(TARGET_BRANCH)

    upstream_changed = get_changed_files(old_main, new_main)
    dist_changed = get_changed_files(old_dist, new_dist)

    conflicts = upstream_changed & dist_changed
    upstream_only = upstream_changed - dist_changed

    return new_main, new_dist, conflicts, upstream_only


# -----------------------------
# JSON IO
# -----------------------------
def load_json(branch: str, path: str) -> Dict:
    content = git_show(branch, path)
    if not content:
        return {}
    return json.loads(content)


def write_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# -----------------------------
# MERGE LOGIC
# -----------------------------
def merge_json(source: Dict, target: Dict) -> Dict:
    merged = {}

    for k in source:
        if k in target:
            merged[k] = target[k]
        else:
            merged[k] = ""

    # preserve existing translations not in source
    for k in target:
        if k not in merged:
            merged[k] = target[k]

    return merged


# -----------------------------
# CONFLICT REPORT
# -----------------------------
def print_conflict(file_path: str):
    print(f"\n🔥 CONFLICT: {file_path}")

    main_json = load_json("main", file_path)
    dist_json = load_json("dist", file_path)

    print("\n--- MAIN ---")
    print(json.dumps(main_json, ensure_ascii=False, indent=2))

    print("\n--- DIST ---")
    print(json.dumps(dist_json, ensure_ascii=False, indent=2))

    # key-level diff
    keys_main = set(main_json.keys())
    keys_dist = set(dist_json.keys())

    print("\n--- KEY DIFF ---")

    added = keys_main - keys_dist
    removed = keys_dist - keys_main
    common = keys_main & keys_dist

    if added:
        print("\n[ADDED in MAIN]")
        for k in added:
            print(" +", k)

    if removed:
        print("\n[REMOVED in MAIN]")
        for k in removed:
            print(" -", k)

    modified = [k for k in common if main_json[k] != dist_json[k]]
    if modified:
        print("\n[MODIFIED]")
        for k in modified:
            print(" *", k)


# -----------------------------
# MAIN SYNC
# -----------------------------
def sync():
    state = init_state_if_missing()

    new_main, new_dist, conflicts, upstream_only = detect_changes(state)

    print(f"\nUpstream changed: {len(upstream_only) + len(conflicts)}")
    print(f"Conflicts: {len(conflicts)}")

    # -----------------------------
    # STEP 1: handle conflicts first
    # -----------------------------
    if conflicts:
        print("\n================ CONFLICT MODE ================\n")
        for f in sorted(conflicts):
            print_conflict(f)

        print("\n❌ Sync stopped due to conflicts.")
        return

    # -----------------------------
    # STEP 2: normal merge
    # -----------------------------
    for file_path in sorted(upstream_only):
        print(f"\nProcessing: {file_path}")

        source = load_json("main", file_path)
        target = load_json("dist", file_path)

        merged = merge_json(source, target)

        write_json(Path(file_path), merged)

    # -----------------------------
    # STEP 3: update state
    # -----------------------------
    state["main"] = new_main
    state["dist"] = new_dist
    save_state(state)

    print("\n✅ Sync complete.")


if __name__ == "__main__":
    sync()