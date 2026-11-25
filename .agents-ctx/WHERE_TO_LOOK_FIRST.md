# Where to Look First

When picking up a task, get oriented before proposing anything.
Read, in this order:

1. The packaging metadata -- what the project is, what it depends
   on, what it exposes.
2. The source of the module the task is about.
3. The shared test fixtures, then the tests for that module --
   they are the behavioral contract.
4. `tox.ini` and `.pre-commit-config.yaml` -- how things get run
   locally and in CI.
5. The main CI/CD workflow.

Here:

1. `pyproject.toml` (setuptools with `setuptools-scm`, the
   metadata, and the `awx_plugins.*` entry point groups AWX
   discovers the plugins through).
2. `src/awx_plugins/credentials/<plugin>.py`, or
   `src/awx_plugins/inventory/plugins.py`. The managed credential
   types live under `src/awx_plugins/credentials/_managed_types/`.
3. There's no `tests/conftest.py`; go straight to the tests --
   `tests/<topic>_test.py`, or `tests/unit/credentials/` for
   `hashivault`.
4. As above, plus `toxfile.py` -- an in-tree tox plugin that
   installs from the lock files and adds the `pip-compile*` envs.
5. `.github/workflows/ci-cd.yml`, which delegates to
   `tox-dev/workflow`'s `reusable-tox.yml`.

Other places worth knowing:

- `dependencies/` -- direct dependencies per tox env under
  `direct/`, and the pinned `lock-files/` generated from them.
  Never edit `lock-files/` by hand -- the `pip-tools` GitHub
  Actions workflow regenerates them (see
  `dependencies/README.md`).
- `docs/` -- Sphinx docs (MyST Markdown and RST);
  `docs/contributing/` includes the root `CONTRIBUTING.md` and a
  testing guide.
- `nitpick-style.toml` -- the style the `nitpick-check` hook
  checks the tool configs against.
