# Security Policy

## Supported Versions

Only the latest `main` branch is actively supported for security updates.

## Reporting a Vulnerability

If you discover a security vulnerability:

1. Do not open a public issue.
2. Email the maintainers with:
   - A clear description of the issue.
   - Reproduction steps and impact.
   - Any proposed remediation.
3. Expect an acknowledgment within 72 hours.
4. Coordinated disclosure will be used for confirmed vulnerabilities.

## Secret Handling Requirements

- Never commit real credentials, API keys, or service-role tokens.
- Use `.env.example` and `.env.supabase.example` templates for local setup.
- Rotate credentials immediately if exposure is suspected.
- Production API keys are stored hashed only; plaintext keys are never persisted.
