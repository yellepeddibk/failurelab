# Protect Main Ruleset

This repository includes `.github/rulesets/protect-main.json` and `scripts/configure_protect_main.py`.

Repository files cannot activate rulesets by themselves. After merge and at least one successful `quality-gate` run, execute:

```bash
GH_TOKEN=<admin_token> python scripts/configure_protect_main.py --repo yellepeddibk/failurelab --dry-run
GH_TOKEN=<admin_token> python scripts/configure_protect_main.py --repo yellepeddibk/failurelab --apply
```
