# GitHub Setup

## Repository Setup

### 1. Create Repository

```bash
gh repo create obscorp/rebrand-service --private --description "Batch document rebranding engine"
```

To use a different GitHub user/org, set the `REBRAND_REPO_URL` environment variable before running `manage.py`:

```bash
export REBRAND_REPO_URL="git@github.com:your-org/rebrand-service.git"
```

### 2. Configure Deploy Key

The management script generates an SSH key automatically. Add the public key as a deploy key:

1. Run `sudo python3 scripts/manage.py install`
2. Copy the printed public key
3. Go to Settings → Deploy Keys → Add deploy key
4. Paste the key, enable "Allow write access" if needed

### 3. Enable Git LFS for Logos

```bash
cd rebrand-service
git lfs install
git lfs track "templates/logos/**/*.png"
git lfs track "templates/logos/**/*.jpg"
git lfs track "templates/logos/**/*.svg"
git add .gitattributes
git commit -m "feat: enable Git LFS for logo assets"
```

### 4. Branch Protection

Recommended branch protection for `main`:
- Require PR reviews (1 reviewer minimum)
- Require status checks to pass (CI workflow)
- Require linear history (no merge commits)

## CI/CD Workflows

### CI (`ci.yaml`)

Triggers on push/PR to `main` and `develop`:
1. **Lint** — `ruff check` and `ruff format --check`
2. **Test** — `pytest` with verbose output
3. **Validate Configs** — `rebrand validate` on all client YAML files

### Rebrand on Config Change (`rebrand.yaml`)

Triggers on push to `main` when `configs/` or `templates/` change:
1. Detects which client configs changed
2. Runs batch rebrand for each changed client
3. Uploads rebranded files as GitHub Actions artifacts (30-day retention)
4. Uploads audit logs as separate artifacts (90-day retention)

## Workflow: Adding a New Client

```bash
# 1. Create branch
git checkout -b feat/add-client-newcorp

# 2. Add config
cp configs/clients/_template.yaml configs/clients/newcorp.yaml
# Edit newcorp.yaml with brand details

# 3. Add logo
mkdir -p templates/logos/newcorp/
cp /path/to/logo.png templates/logos/newcorp/logo.png

# 4. Validate locally
rebrand validate

# 5. Commit and PR
git add configs/clients/newcorp.yaml templates/logos/newcorp/
git commit -m "feat: add newcorp brand config"
git push -u origin feat/add-client-newcorp
gh pr create --title "feat: add NewCorp brand config" --body "Adds brand config and logo for NewCorp."
```

## Conventional Commits

All commits follow conventional commit format:
- `feat:` — New client config, new feature
- `fix:` — Bug fix in rebranding logic
- `refactor:` — Code restructure, no behavior change
- `docs:` — Documentation updates
- `ci:` — CI/CD workflow changes
- `chore:` — Dependency updates, tooling changes
