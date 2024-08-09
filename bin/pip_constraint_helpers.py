"""Shared functions for platform detection."""

from __future__ import annotations

import pathlib
import platform
import shlex
import subprocess  # noqa: S404 -- pip/pip-tools don't have importable APIs
import sys


PYTHON_IMPLEMENTATION_MAP = {  # noqa: WPS407
    'cpython': 'cp',
    'ironpython': 'ip',
    'jython': 'jy',
    'python': 'py',
    'pypy': 'pp',
}
PYTHON_IMPLEMENTATION = platform.python_implementation()


def get_runtime_python_tag() -> str:
    """Identify the Python tag of the current runtime.

    :returns: Python tag.
    """
    python_minor_ver = sys.version_info[:2]

    try:
        sys_impl = sys.implementation.name
    except AttributeError:
        sys_impl = PYTHON_IMPLEMENTATION.lower()

    python_tag_prefix = PYTHON_IMPLEMENTATION_MAP.get(sys_impl, sys_impl)

    python_minor_ver_tag = ''.join(map(str, python_minor_ver))

    return f'{python_tag_prefix !s}{python_minor_ver_tag !s}'


def get_constraint_file_path(  # noqa: WPS210 -- no way to drop vars
    req_dir: pathlib.Path | str,
    toxenv: str,
    python_tag: str,
) -> pathlib.Path:
    """Identify the constraints filename for the current environment.

    :param req_dir: Requirements directory.
    :type req_dir: pathlib.Path | str
    :param toxenv: tox testenv.
    :type toxenv: str
    :param python_tag: Python tag.
    :type python_tag: str
    :returns: Constraints filename for the current environment.
    """
    sys_platform = sys.platform
    platform_machine = platform.machine().lower()

    if toxenv in {'py', 'python'}:
        env_prefix = 'pypy' if PYTHON_IMPLEMENTATION == 'PyPy' else 'py'
        python_ver_num = python_tag[2:]
        toxenv = f'{env_prefix}{python_ver_num}'

    if sys_platform == 'linux2':
        sys_platform = 'linux'

    constraint_name = (
        f'{toxenv}-{python_tag}-{sys_platform}-{platform_machine}'
    )
    return (pathlib.Path(req_dir) / constraint_name).with_suffix('.txt')


def make_pip_cmd(
    pip_args: list[str],
    constraint_file_path: pathlib.Path,
) -> list[str]:
    """Inject a lockfile constraint into the pip command if present.

    :param pip_args: pip arguments.
    :type pip_args: list[str]
    :param constraint_file_path: Path to a ``constraints.txt``-compatible file.
    :type constraint_file_path: pathlib.Path

    :returns: pip command.
    """
    pip_cmd = [sys.executable, '-Im', 'pip'] + pip_args
    if constraint_file_path.is_file():
        pip_cmd += ['--constraint', str(constraint_file_path)]
    else:
        print(  # noqa: WPS421
            'WARNING: The expected pinned constraints file for the current '
            f'env does not exist (should be "{constraint_file_path !s}").',
        )
    return pip_cmd


def run_cmd(cmd: list[str] | tuple[str, ...]) -> None:
    """Invoke a shell command after logging it.

    :param cmd: The command to invoke.
    :type cmd: list[str] | tuple[str, ...]
    """
    escaped_cmd = shlex.join(cmd)
    print(f'Invoking the following command: {escaped_cmd !s}')  # noqa: WPS421
    subprocess.check_call(cmd)  # noqa: S603
