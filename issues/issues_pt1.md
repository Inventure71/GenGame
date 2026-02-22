# Audit Findings (Part 1)

Format per finding:
- File path
- Issue type
- Severity
- Explanation
- Why it is a problem
- Concrete proposed fix
- Optional refactor suggestion

## Finding 1
- File path: `.env`
- Issue type: Secret exposure / credential management
- Severity: Critical
- Explanation: The workspace `.env` file contained hard-coded live-looking API credentials (Gemini and OpenAI keys).
- Why it is a problem: Exposed credentials can be abused immediately, incur financial loss, leak data, and provide unauthorized access. If this file is ever committed or shared, compromise persists in history/copies.
- Concrete proposed fix: Replace committed secrets with placeholders, rotate/revoke all exposed keys immediately, move real values to untracked runtime secret storage, and add `.env.example` for safe onboarding.
- Optional refactor suggestion: Add startup validation that refuses to run when keys match obvious placeholder/compromised formats and enforce secret-scanning in CI.
