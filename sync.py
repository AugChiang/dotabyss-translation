import json
import subprocess
from pathlib import Path
from typing import Dict, Tuple, List, Set

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
        "story-only": get_commit(TARGET_BRANCH)
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
    old_story_only = state["story-only"]

    new_main = get_commit(SOURCE_BRANCH)
    new_story_only = get_commit(TARGET_BRANCH)

    upstream_changed = get_changed_files(old_main, new_main)
    story_only_changed = get_changed_files(old_story_only, new_story_only)

    conflicts = upstream_changed & story_only_changed
    upstream_only = upstream_changed - story_only_changed

    return new_main, new_story_only, conflicts, upstream_only


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
    story_only_json = load_json("story-only", file_path)

    # print("\n--- MAIN ---")
    # print(json.dumps(main_json, ensure_ascii=False, indent=2))

    # print("\n--- STORY-ONLY ---")
    # print(json.dumps(story_only_json, ensure_ascii=False, indent=2))

    # key-level diff
    keys_main = set(main_json.keys())
    keys_story_only = set(story_only_json.keys())

    print("\n--- KEY DIFF ---")

    added = keys_main - keys_story_only
    removed = keys_story_only - keys_main
    common = keys_main & keys_story_only

    if added:
        print("\n[ADDED in MAIN]")
        for k in added:
            print(" +", k)

    if removed:
        print("\n[REMOVED in MAIN]")
        for k in removed:
            print(" -", k)

    modified = [k for k in common if main_json[k] != story_only_json[k]]
    if modified:
        print("\n[MODIFIED]")

        for k in modified:
            old_val = story_only_json.get(k)
            new_val = main_json.get(k)

            print(f"\nKEY: {k}")
            print("  - OLD:", old_val)
            print("  + NEW:", new_val)

# def resolve_conflict_interactive(file_path: str):
#     print(f"\n🔥 CONFLICT FILE: {file_path}\n")

#     main_json = load_json("main", file_path)
#     story_only_json = load_json("story-only", file_path)

#     merged = dict(story_only_json)  # start from current translation

#     keys = set(main_json.keys()) | set(story_only_json.keys())

#     for key in sorted(keys):
#         main_val = main_json.get(key)
#         story_only_val = story_only_json.get(key)

#         # no conflict
#         if main_val == story_only_val:
#             merged[key] = story_only_val
#             continue

#         print("\n" + "=" * 50)
#         print(f"KEY: {key}")
#         print(f"MAIN: {main_val}")
#         print(f"STORY-ONLY: {story_only_val}")

#         print("\nChoose action:")
#         print("  [1] keep MAIN")
#         print("  [2] keep STORY-ONLY")
#         print("  [3] edit manually")
#         print("  [Enter] default STORY-ONLY")

#         choice = input("> ").strip()

#         if choice == "1":
#             merged[key] = main_val if main_val is not None else ""
#         elif choice == "2" or choice == "":
#             merged[key] = story_only_val
#         elif choice == "3":
#             new_val = input("Enter new value: ")
#             merged[key] = new_val
#         else:
#             merged[key] = story_only_val

#     # write resolved file
#     write_json(Path(file_path), merged)

#     print(f"\n✅ Resolved: {file_path}")

def resolve_conflict_interactive(file_path: str):
    print(f"\n🔥 CONFLICT FILE: {file_path}\n")

    main_json = load_json("main", file_path)
    story_only_json = load_json("story-only", file_path)

    print("Choose file-level action:")
    print("  [A] Accept ALL from MAIN (overwrite story-only file)")
    print("  [S] Keep ALL STORY-ONLY (ignore upstream changes)")
    print("  [C] Custom per-key resolution")

    file_choice = input("> ").strip().lower()

    # -----------------------------
    # OPTION A: accept main fully
    # -----------------------------
    if file_choice == "a":
        print("→ Overwriting with MAIN version")
        write_json(Path(file_path), main_json)
        print("✅ Done (MAIN accepted)")
        return

    # -----------------------------
    # OPTION S: keep story-only fully
    # -----------------------------
    if file_choice == "s":
        print("→ Keeping STORY-ONLY version unchanged")
        return

    # -----------------------------
    # OPTION C: per-key resolution
    # -----------------------------
    print("\nEntering per-key resolution...\n")

    merged = dict(story_only_json)
    keys = set(main_json.keys()) | set(story_only_json.keys())

    for key in sorted(keys):
        main_val = main_json.get(key)
        story_only_val = story_only_json.get(key)

        if main_val == story_only_val:
            merged[key] = story_only_val
            continue

        print("\n" + "=" * 60)
        print(f"KEY: {key}")
        print(f"MAIN: {main_val}")
        print(f"STORY-ONLY: {story_only_val}")

        print("\nChoose:")
        print("  [1] keep MAIN")
        print("  [2] keep STORY-ONLY")
        print("  [3] edit manually")
        print("  [Enter] default STORY-ONLY")

        choice = input("> ").strip()

        if choice == "1":
            merged[key] = main_val if main_val is not None else ""
        elif choice == "2" or choice == "":
            merged[key] = story_only_val
        elif choice == "3":
            merged[key] = input("New value: ")
        else:
            merged[key] = story_only_val

    write_json(Path(file_path), merged)
    print(f"\n✅ Resolved: {file_path}")


# -----------------------------
# MAIN SYNC
# -----------------------------
def sync():
    state = init_state_if_missing()

    new_main, new_story_only, conflicts, upstream_only = detect_changes(state)

    print(f"\nUpstream changed: {len(upstream_only) + len(conflicts)}")
    print(f"Conflicts: {len(conflicts)}")

    if conflicts:
        print("\n🔥 ENTERING INTERACTIVE CONFLICT MODE\n")

        for f in sorted(conflicts):
            resolve_conflict_interactive(f)

        print("\n✅ All conflicts resolved.")

        # -----------------------------
        # NEW: ask for commit
        # -----------------------------
        choice = input(f"\nDo you want to commit changes to {TARGET_BRANCH} branch? (y/n): ").strip().lower()

        if choice == "y":
            print("\n📦 Committing changes...")

            subprocess.run(["git", "add", "."])
            subprocess.run(["git", "commit", "-m", "Resolve translation conflicts"])
            subprocess.run(["git", "push", "origin", TARGET_BRANCH])

            print("✅ Pushed to dist branch")

        else:
            print("⚠️ Skipped commit. You can commit manually later.")

        # IMPORTANT: update state AFTER resolution
        state["main"] = new_main
        state["story-only"] = new_story_only
        save_state(state)

        print("\n🧠 Sync state updated.")
        return

if __name__ == "__main__":
    sync()