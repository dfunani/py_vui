# Publishing py_vui for everyone

This guide is for **maintainers** who want to ship releases on PyPI and GitHub. End users only need `pip install py-vui[gui]` once the package is published.

## Prerequisites (you do these once)

1. **PyPI account** — register at [pypi.org](https://pypi.org) and [test.pypi.org](https://test.pypi.org).
2. **API token** — on each site: Account settings → API tokens → “Add API token” (scope: entire account or project `py-vui`). Save the token; it is shown only once.
3. **Name availability** — on PyPI, search for `py-vui`. If the name is taken, change `name` in `pyproject.toml` before the first upload.
4. **Optional: GitHub Actions** — for automated uploads on git tags, add a repository secret:
   - GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `PYPI_API_TOKEN`
   - Value: your PyPI API token (with upload scope for `py-vui`)

## Version bumps

Before every release, bump the version in `pyproject.toml`:

```toml
version = "0.1.1"   # example
```

Commit that change on `main` (or your release branch).

## Build artifacts (local)

From the repository root:

```bash
# With uv (this repo):
uv pip install build twine
uv run python -m build

# Or any Python 3.12+ environment:
python -m pip install --upgrade build twine
python -m build
```

This creates `dist/py_vui-<version>.tar.gz` and `dist/py_vui-<version>-py3-none-any.whl`.

## Test on TestPyPI first (recommended)

```bash
twine upload --repository testpypi dist/*

# In a fresh virtualenv, verify install:
python -m venv /tmp/py-vui-test
source /tmp/py-vui-test/bin/activate   # Windows: \tmp\py-vui-test\Scripts\activate
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "py-vui[gui]==<YOUR_VERSION>"
py_vui
deactivate
```

Replace `<YOUR_VERSION>` with the version you just uploaded (e.g. `0.1.0`).

## Publish to PyPI (production)

```bash
twine upload dist/*
```

When prompted:

- **Username:** `__token__`
- **Password:** your PyPI API token (including the `pypi-` prefix)

Or non-interactive:

```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-XXXX twine upload dist/*
```

After upload, anyone can install:

```bash
pip install "py-vui[gui]"
py_vui
```

PyPI normalizes the project name `py_vui` in `pyproject.toml` to **`py-vui`** on install.

## Git tag + GitHub Release

Tag the release commit and push:

```bash
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
```

On GitHub: **Releases → Draft a new release** → choose tag `v0.1.0`, add release notes (features, fixes, Python version requirement).

If the GitHub Action workflow is enabled (see below), pushing a tag matching `v*` also uploads to PyPI automatically.

## Automated PyPI upload (GitHub Actions)

The workflow `.github/workflows/publish-pypi.yml` runs on pushes of tags `v*.*.*` (e.g. `v0.1.0`). It builds with `python -m build` and uploads with `twine` using `PYPI_API_TOKEN`.

**You must** add the `PYPI_API_TOKEN` secret (see Prerequisites). Without it, the workflow fails at upload time.

To trigger manually after fixing secrets: re-push the tag or use “Re-run workflow” in the Actions tab.

## Optional: standalone app bundles (not required for PyPI)

PyPI installs the editor as a Python CLI. For users who do not want Python on their PATH, you can later add PyInstaller/briefcase builds and attach `.app` / `.exe` assets to GitHub Releases. That is separate from the PyPI flow above.

## Checklist per release

- [ ] Bump `version` in `pyproject.toml`
- [ ] Update README changelog section (if you keep one) or GitHub release notes
- [ ] `uv run pytest -q` and `uv run ruff check src`
- [ ] `python -m build`
- [ ] `twine upload --repository testpypi dist/*` and smoke-test install
- [ ] `twine upload dist/*`
- [ ] `git tag -a vX.Y.Z -m "Release X.Y.Z"` and `git push origin vX.Y.Z`
- [ ] GitHub Release with notes
