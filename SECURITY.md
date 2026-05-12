# Security Policy

This tool handles private operational context and generated repo-local agent files. Treat privacy boundary regressions as security issues.

## Report

Until a dedicated channel exists, report security issues privately to the maintainer instead of opening a public issue.

## High Priority Areas

- Client repo leakage of `corp-private` material
- Incorrect source trust or pin validation
- Unsafe writes to tracked repo content
- Incorrect repo matching that applies the wrong overlay
