# Security Policy — NoireBox

NoireBox is itself a security tool: it must be designed and treated as such.

## Reporting a vulnerability

**Do not open a public issue for a vulnerability.**

Preferred contact: open a GitHub *Security Advisory* (Security → Report a vulnerability)
for the repository, or contact the maintainer privately.

Target response time: **72 hours** to assess; target fix time: **7 days** for
vulnerabilities affecting the integrity of the journal (the core value of the project).

## Scope — what counts as a vulnerability

- Any journal tampering **not detected** by `verify_chain` or
  `verifier/verifier.py` (the core contract of the project)
- Guardrail bypass that makes an attack undetectable
- Private key leakage caused by a code defect (permissions, logs, export)

## Security assumptions we document, not hide

- The private key lives on the server (chmod 600). An attacker with disk access **and** the key can
  forge a complete chain — the externally published attestation (head hash) remains the countermeasure.
  HSM/KMS migration is in the roadmap.
- The guardrail is probabilistic (regex + ML): it flags issues but does not block them.
  False negatives are assumed and measured (`tests/test_ml_guardrail.py`).

## Coordinated disclosure

Fixes are published with credit to the reporter unless otherwise requested, in the CHANGELOG.
