# dotabyss-transltions
This branch only fetch the story content.
If you only need the translations of `novels` (stories), you are at the right place!

## How to add another folder to this branch?
For example, to add `folderC` from main branch to this branch:

```bash
git checkout story-only
git checkout main -- folderC
git commit -m "Add folderC from main"
```

Also, remember to add `folderC` to the `FOLDERS` list in `sync.py`, or the python script will ignore it.


## How to handle conflicts?
When the main branch has updated, run `python sync.py` and it will guide you to solve the conflicts.
(Basically, run sync when main branch is updated, or it will keep the content of this branch.)