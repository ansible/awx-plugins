# Testing Guide

This document explains how to install dependencies and run tests for awx-plugins.

## Prerequisites

- Python 3
- [tox](https://tox.wiki/)

## Quick Start

tox handles dependency installation and test execution automatically:

```bash
# Run the test suite under the current Python:
tox r -e py -qq

# Run tests for a specific Python version:
tox r -e py311 -qq
tox r -e py312 -qq
tox r -e py313 -qq

# Run the linters
tox r -e pre-commit

# Run just MyPy against Python 3.14, will hint how to open the HTML
# report on type accuracy locally:
tox r -e pre-commit -qq -- mypy-py314 --all-files

# Build the docs:
tox r -e build-docs -qq
```
