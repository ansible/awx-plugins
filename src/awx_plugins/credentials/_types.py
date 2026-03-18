"""Shared interface type definitions for credential plugin schemes."""

import typing as _t


class FieldDict(_t.TypedDict):
    """A single UI field schema."""

    id: str
    label: str
    type: _t.NotRequired[str]
    format: _t.NotRequired[str]
    secret: _t.NotRequired[bool]
    multiline: _t.NotRequired[bool]
    help_text: _t.NotRequired[str]
    default: _t.NotRequired[str | bool]
    choices: _t.NotRequired[list[str]]
    internal: _t.NotRequired[bool]


class MetadataDict(_t.TypedDict):
    """Schema for input metadata."""

    id: str
    label: _t.NotRequired[str]
    type: _t.NotRequired[str]
    help_text: _t.NotRequired[str]
    multiline: _t.NotRequired[bool]
    default: _t.NotRequired[str | bool]
    choices: _t.NotRequired[list[str]]


class PluginInputs(_t.TypedDict):
    """Schema for a collection of plugin input fields."""

    fields: list[FieldDict]
    metadata: list[MetadataDict]
    required: list[str]
