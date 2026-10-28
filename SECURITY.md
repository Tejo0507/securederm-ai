# Security Policy

SecureDerm AI handles sensitive clinical workflows, so security reports are taken seriously.

## Reporting a vulnerability

**Please don't open a public issue.** Use GitHub's private reporting instead:
[Report a vulnerability](https://github.com/Tejo0507/securederm-ai/security/advisories/new).

Include what you found, how to reproduce it, and the impact you expect. You will get an acknowledgement, and fixes are developed privately before details are published.

## Scope

In scope: the aggregation server, the hospital node client, the web backend (authentication, sessions, uploads, prediction and history endpoints) and the dashboard.

Particularly valuable reports: ways to read another hospital's data, bypass authentication or CSRF protection, poison or exfiltrate the global model, defeat the differential-privacy accounting, or make patient images or identifiers appear in storage or logs.

## What's already in place

See the [Security section of the README](README.md#security) for the hardening that exists today (httpOnly sessions with CSRF protection, verified e-mail accounts, PBKDF2 password hashing, per-account rate limits, metadata-stripped uploads, an audit trail, and more).

## Supported versions

Fixes land on `main`; run the latest commit.
