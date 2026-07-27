# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.2.x | ✅ |
| < 0.2 | ❌ |

Security fixes are applied to the latest released minor version.

## Scope

Core analysis is local-first and makes no network calls. The optional
interpretation layer (`failurelab.interpret`) is the only component that can
transmit data to a third party, and only when you explicitly construct a
provider and call it. It is disabled by default and is never activated by the
presence of an environment variable.

Provider credentials are supplied by you, are never stored, logged, or included
in report provenance, and FailureLab does not read `.env` files.

## Reporting a Vulnerability

Please report vulnerabilities privately via GitHub Security Advisories. Do not
open public issues for sensitive reports.
