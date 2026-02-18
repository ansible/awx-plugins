# Testing Guide

This document explains how to install dependencies and run tests for awx-plugins.

## Prerequisites

- Python 3
- [tox](https://tox.wiki/)

## Quick Start

tox handles dependency installation and test execution automatically:

```bash
# Run the test suite
tox r -e py -qq

# Run tests for a specific Python version
tox r -e py311
tox r -e py312
tox r -e py313
```