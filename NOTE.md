## Future update workflow

Update main:
```bash
git checkout main
git fetch upstream
git merge upstream/main
```
Then reapply your translations:
```bash
git checkout custom-translations
git rebase main
```