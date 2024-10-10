# pylint: disable=invalid-name  # <-- demands all settings to be uppercase
"""Configuration of Sphinx documentation generator."""

import os
import sys
from importlib.metadata import version as _retrieve_metadata_version_for
from pathlib import Path
from tomllib import loads as _parse_toml

from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment


# isort: split

from docutils.nodes import literal, reference


# -- Path setup --------------------------------------------------------------

DOCS_ROOT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT_DIR = DOCS_ROOT_DIR.parent.resolve()
PROJECT_SRC_DIR = PROJECT_ROOT_DIR / 'src'
IS_RTD_ENV = os.getenv('READTHEDOCS', 'False') == 'True'
IS_RELEASE_ON_RTD = (
    IS_RTD_ENV
    and os.environ['READTHEDOCS_VERSION_TYPE'] == 'tag'
)
tags: set[str]
if IS_RELEASE_ON_RTD:
    # pylint: disable-next=used-before-assignment
    tags.add('is_release')  # noqa: F821
elif IS_RTD_ENV:
    # pylint: disable-next=used-before-assignment
    tags.add('is_unversioned')  # noqa: F821


# Make in-tree extension importable in non-tox setups/envs, like RTD.
# Refs:
# https://github.com/readthedocs/readthedocs.org/issues/6311
# https://github.com/readthedocs/readthedocs.org/issues/7182
sys.path.insert(0, str(DOCS_ROOT_DIR / '_ext'))


project = _parse_toml(
    (PROJECT_ROOT_DIR / 'pyproject.toml').read_text(),
)['project']['name']
author = 'Ansible maintainers and contributors'
copyright = author  # pylint: disable=redefined-builtin

# NOTE: Using the "unversioned" static string improves rebuild
# NOTE: performance by keeping the doctree cache valid for longer.

# The full version, including alpha/beta/rc tags
release = (
    # pylint: disable-next=used-before-assignment
    'unversioned' if tags.has('is_unversioned')  # noqa: F821
    else _retrieve_metadata_version_for(project)
)

# The short X.Y version
version = (
    # pylint: disable-next=used-before-assignment
    'unversioned' if tags.has('is_unversioned')  # noqa: F821
    else '.'.join(release.split('.')[:2])
)

rst_epilog = f"""
.. |project| replace:: {project}
.. |release_l| replace:: ``v{release}``
"""


extensions = [
    # Stdlib extensions:
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',  # autocreate section targets for refs
    'sphinx.ext.coverage',  # for invoking with `-b coverage`
    'sphinx.ext.doctest',  # for invoking with `-b doctest`
    'sphinx.ext.intersphinx',

    # Third-party extensions:
    'myst_parser',  # extended markdown; https://pypi.org/project/myst-parser/
    'sphinx_issues',  # implements `:issue:`, `:pr:` and other GH-related roles
    'sphinx_tabs.tabs',
    'sphinxcontrib.apidoc',

    # In-tree extensions:
    'spelling_stub_ext',  # auto-loads `sphinxcontrib.spelling` if installed
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

root_doc = 'index'

# -- Options for HTML output -------------------------------------------------

html_static_path = ['_static']
html_theme = 'furo'
html_theme_options = {
    'dark_logo': 'images/Ansible-Mark-RGB_White.svg',
    'light_logo': 'images/Ansible-Mark-RGB_Black.svg',
}

# -- Options for myst_parser extension ---------------------------------------

myst_enable_extensions = [
    'colon_fence',  # allow to optionally use ::: instead of ```
    'deflist',
    'html_admonition',  # allow having HTML admonitions
    'html_image',  # allow HTML <img> in Markdown
    'linkify',  # auto-detect URLs @ plain text, needs myst-parser[linkify]
    'replacements',  # allows Jinja2-style replacements
    'smartquotes',  # use "cursive" quotes
    'substitution',  # replace common ASCII shortcuts into their symbols
]
myst_substitutions = {
    'project': project,
    'release': release,
    'release_l': f'`v{release}`',
    'version': version,
}
myst_heading_anchors = 3

# -- Options for sphinxcontrib.apidoc extension ------------------------------

apidoc_excluded_paths = []
apidoc_extra_args = [
    '--implicit-namespaces',
    '--private',  # include “_private” modules
]
apidoc_module_dir = str(PROJECT_SRC_DIR / 'awx_plugins')
apidoc_module_first = False
apidoc_output_dir = 'pkg'
apidoc_separate_modules = True
apidoc_template_dir = str(DOCS_ROOT_DIR / 'pkg' / '_templates/')
apidoc_toc_file = None

# -- Options for sphinxcontrib.spelling extension ----------------------------

spelling_ignore_acronyms = True
spelling_ignore_importable_modules = True
# PyPI lookup because of https://github.com/sphinx-contrib/spelling/issues/227
spelling_ignore_pypi_package_names = False
spelling_ignore_python_builtins = True
spelling_ignore_wiki_words = True
spelling_show_suggestions = True
spelling_word_list_filename = [
    'spelling_wordlist.txt',
]

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# -- Options for linkcheck builder -------------------------------------------

linkcheck_ignore = [
    r'https?://localhost:\d+/',  # local URLs
    r'https://codecov\.io/gh(/[^/]+){2}/branch/master/graph/badge\.svg',
    r'https://github\.com(/[^/]+){2}/actions',  # 404 if no auth
    r'^https://chat\.ansible\.im/#',  # these render fully on front-end
    r'^https://matrix\.to/#',  # these render fully on front-end from anchors
]
linkcheck_workers = 25

# -- Options for sphinx.ext.autosectionlabel extension -----------------------

# Ref:
# https://www.sphinx-doc.org/en/master/usage/extensions/autosectionlabel.html
autosectionlabel_maxdepth = 1  # mitigate Towncrier nested subtitles collision

# -- Options for sphinx_issues extension -------------------------------------

# https://github.com/sloria/sphinx-issues#installation-and-configuration

issues_github_path = 'ansible/awx_plugins'

# -- Options for sphinx_tabs extension ---------------------------------------

# Ref:
# * https://github.com/djungelorm/sphinx-tabs/issues/26#issuecomment-422160463
sphinx_tabs_valid_builders = ['linkcheck']  # prevent linkcheck warning

# -- Options enforcing strict mode -------------------------------------------

# Ref: https://github.com/python-attrs/attrs/pull/571/files\
#      #diff-85987f48f1258d9ee486e3191495582dR82
default_role = 'any'

nitpicky = True

# NOTE: consider having a separate ignore file
# Ref: https://stackoverflow.com/a/30624034/595220
nitpick_ignore = [
    # temporarily listed ('role', 'reference') pairs that Sphinx cannot resolve
]


def _replace_missing_boto3_reference(
    app: Sphinx,
    env: BuildEnvironment,
    node: pending_xref,
    contnode: literal,
) -> reference | None:
    if (node.get('refdomain'), node.get('reftype')) != ('py', 'class'):
        return None

    boto3_type_uri_map = {
        'AssumeRoleResponseTypeDef': 'type_defs/#assumeroleresponsetypedef',
        'CredentialsTypeDef': 'type_defs/#credentialstypedef',
        'STSClient': 'client/#stsclient',
    }
    ref_target = node.get('reftarget', '')

    try:
        return reference(
            ref_target,
            ref_target,
            internal=False,
            refuri='https://youtype.github.io/boto3_stubs_docs/'
            f'mypy_boto3_sts/{boto3_type_uri_map[ref_target]}',
        )
    except KeyError:
        return None


def setup(app: Sphinx) -> dict[str, bool | str]:
    """Register project-local Sphinx extension-API customizations."""

    app.connect('missing-reference', _replace_missing_boto3_reference)

    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
        'version': release,
    }
