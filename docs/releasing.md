# Publishing and releasing py_vui

How to ship a new version to PyPI and GitHub. The PyPI package name is `py-vui`; the import and CLI name is `py_vui`.

What a release produces:

| Output | Where | Built by |
|---|---|---|
| sdist + wheel | PyPI (`pip install py-vui`) | `build-dist` + `pypi` jobs |
| Desktop bundles (macOS, Windows, Linux zips) | GitHub Release assets | `bundles` job (PyInstaller) |
| Release notes | GitHub Release | `github-release` job |

All of this runs from `.github/workflows/publish-pypi.yml` when a tag matching `v*` is pushed.
Day-to-day CI (lint, tests on 3 OSes × Python 3.12/3.13, wheel smoke test) is `.github/workflows/ci.yml`.

## One-time setup

### 1. PyPI account and project
1. Create accounts on [pypi.org](https://pypi.org) and [test.pypi.org](https://test.pypi.org) (enable 2FA).
2. The name `py-vui` must be free on PyPI. If it is taken, change `name` in `pyproject.toml` (the import name stays `py_vui`).

### 2. Authenticate the workflow (pick one)
**Trusted Publishing (recommended, no secrets):**
1. On PyPI go to *Your projects ▸ Publishing* (for a brand-new project: *Account settings ▸ Publishing ▸ Add a pending publisher*).
2. Add a GitHub publisher: owner `dfunani`, repository `py_vui`, workflow file `publish-pypi.yml`, environment `pypi`.
3. In GitHub: *Settings ▸ Environments ▸ New environment* named `pypi` (optionally require a reviewer to approve each release).

**API token (fallback):**
1. On PyPI create an API token scoped to the project.
2. In GitHub: *Settings ▸ Secrets and variables ▸ Actions* add `PYPI_API_TOKEN`.
   The workflow passes it to the publish action; leave the secret unset when using Trusted Publishing.

### 3. GitHub permissions
*Settings ▸ Actions ▸ General ▸ Workflow permissions* must allow the workflow to run. The release job requests `contents: write` itself.

## Release checklist

1. **Start from a green `main`.**
   ```bash
   git checkout main && git pull
   python -m venv .venv && .venv/bin/pip install -e ".[dev]"
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
   .venv/bin/ruff check src tools packaging
   python tools/gen_docs.py --check        # generated doc tables are current
   ```
   Optional extra coverage if you have the environments: run the Tk/CustomTkinter and Kivy adapter tests
   (see [CONTRIBUTING.md](../CONTRIBUTING.md) for the test environments).
2. **Bump the version** (it must match in both places):
   - `pyproject.toml` → `[project] version`
   - `src/py_vui/__init__.py` → `__version__`
3. **Update `CHANGELOG.md`**: move *Unreleased* items under a new `## [X.Y.Z] - YYYY-MM-DD` heading.
4. **Build and check locally:**
   ```bash
   rm -rf dist build
   .venv/bin/python -m build
   .venv/bin/twine check dist/*
   ```
5. **Dry run on TestPyPI (recommended for new versions):**
   ```bash
   .venv/bin/twine upload --repository testpypi dist/*
   python -m venv /tmp/rel && /tmp/rel/bin/pip install --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ py-vui==X.Y.Z
   /tmp/rel/bin/py_vui --version && /tmp/rel/bin/py_vui templates
   ```
   TestPyPI rejects re-uploads of the same version, so a failed dry run means bumping to a new version.
6. **Merge the version bump to `main`** (via PR), then tag that commit:
   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "py_vui X.Y.Z"
   git push origin vX.Y.Z
   ```
   The tag must equal `v` + the version in `pyproject.toml`.
7. **Watch the workflow** (*Actions ▸ Release*): `build-dist` → `pypi` + `bundles` → `github-release`.
   If the `pypi` job uses a protected `pypi` environment, approve it when prompted.
8. **Verify:**
   ```bash
   python -m venv /tmp/verify && /tmp/verify/bin/pip install py-vui==X.Y.Z
   /tmp/verify/bin/py_vui --version
   ```
   Open the GitHub Release page and check the three bundles are attached and the notes look right.

## Versioning

[Semantic Versioning](https://semver.org). While below 1.0, minor bumps (`0.X.0`) may include breaking changes to the project file format or CLI; patch bumps (`0.2.Y`) are fixes only.
The project file has its own `schemaVersion` (currently `"2"`). Changing it requires a migration in `src/py_vui/core/migrate.py` and a test; older files must keep loading.

## Building a desktop bundle locally

```bash
.venv/bin/pip install pyinstaller
.venv/bin/python packaging/build_bundle.py --name py_vui-local
# → dist-bundle/py_vui-local.zip
```
Bundles are unsigned. macOS Gatekeeper and Windows SmartScreen will warn on first launch; code signing and
notarisation need your own certificates and are not part of the workflow.

## Manual PyPI upload (if CI is unavailable)

```bash
rm -rf dist && .venv/bin/python -m build
.venv/bin/twine upload dist/*     # username __token__, password = your API token
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `pypi` job: *invalid-publisher* / 403 | Trusted publisher details don't match exactly (owner, repo, workflow file `publish-pypi.yml`, environment `pypi`), or neither Trusted Publishing nor `PYPI_API_TOKEN` is set up. |
| *File already exists* | That version was already uploaded. PyPI versions are immutable: bump the version and re-tag. |
| Wheel installs but `py_vui` can't find templates | Package data is configured in `pyproject.toml` (`[tool.setuptools.package-data]`); rebuild and check with `unzip -l dist/*.whl`. |
| Bundle job fails on Linux with Qt errors | The runner needs the libraries listed in `ci.yml` (`libegl1`, `libxkbcommon0`, `libxcb-*`); add them to the `bundles` job. |
| Tag pushed but nothing ran | The tag must match `v*` and the workflow file must exist on the tagged commit. |
| Need to retract a release | On PyPI *yank* the version (don't delete), fix, and release the next patch version. Delete the GitHub Release and tag only if it was never published. |
