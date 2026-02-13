# Testing Guide

This document explains how to install dependencies and run tests for awx-plugins.

## Prerequisites

- Python 3.11 due to compatibility issues
- [tox](https://tox.wiki/) (recommended) or pip

## Quick Start

tox handles dependency installation and test execution automatically:

```bash
# Install tox
pip install tox

# Run the full test suite
tox r -e py

# Run tests for a specific Python version
tox r -e py311
tox r -e py312
tox r -e py313
```

## Code Quality Checks

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Or run pre-commit directly
pre-commit run --all-files
```
