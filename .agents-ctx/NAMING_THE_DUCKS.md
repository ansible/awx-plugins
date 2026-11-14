# Naming the Ducks

Canonical names for this project, and how to refer to it in
prose. Other files in `.agents-ctx/` (and any generated content)
should say "the project" rather than hardcoding one of these --
reach for a specific name only when the distinction actually
matters (e.g. citing a package, an import, or a repository URL).

## Distribution / PyPI name: `awx-plugins-core`

The installable, published name -- recorded in
`pyproject.toml`'s `[project].name` per PEP 621. This is also
the preferred way to refer to the project by name in prose.

## Python import names: `awx_plugins.credentials`, `awx_plugins.inventory`

The plugins live under `awx_plugins`, a PEP 420 implicit namespace
package shared with other distributions, such as
`awx_plugins.interfaces`. None of `src/awx_plugins/` and its
sub-packages has an `__init__.py` -- don't add one. AWX finds the
plugins through the `awx_plugins.*` entry point groups declared in
`pyproject.toml`.

## GitHub repository slug: `ansible/awx-plugins`

Close to, but not the same as, the distribution name above. Use
it verbatim when it's actually the repository being referenced
(URLs, `gh` invocations, PR/issue citations) -- not as a stand-in
for the project's name in prose.

## Don't confuse it with `ansible/awx_plugins.interfaces`

`ansible/awx_plugins.interfaces` is a separate repository,
publishing `awx_plugins.interfaces` -- the interfaces this
project's plugins implement and that AWX consumes. Say which one
is meant.
