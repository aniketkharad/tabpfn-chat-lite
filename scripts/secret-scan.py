#!/usr/bin/env python3
"""Secret scan script: verifies no real API keys or sensitive credentials are in source code."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Patterns that match potential real credentials (not mock/dev strings)
PATTERNS = [
    (r"AIzaSy[A-Za-z0-9_-]{33}", "Google / Gemini API Key"),
    (r"tabpfn_[a-zA-Z0-9]{32,}", "TabPFN Live Token"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "Private Key"),
]

IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".wrangler",
}

IGNORED_FILES = {
    ".env",
}


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    findings = []
    for pattern, desc in PATTERNS:
        matches = re.findall(pattern, content)
        for m in matches:
            if "mock_" in m or "dev_" in m or "example" in m or "0000000" in m:
                continue
            findings.append(f"{desc} match: {m[:6]}... in {path.relative_to(ROOT_DIR)}")
    return findings


def main() -> int:
    print("=" * 60)
    print("SECRET SCAN VERIFICATION")
    print("=" * 60)

    findings: list[str] = []
    for p in ROOT_DIR.rglob("*"):
        if p.is_file():
            if any(part in IGNORED_DIRS for part in p.parts):
                continue
            if p.name in IGNORED_FILES:
                continue
            findings.extend(scan_file(p))

    if findings:
        print("❌ POTENTIAL SECRETS DETECTED:")
        for f in findings:
            print(f"  - {f}")
        return 1

    print("✓ Zero real secrets or exposed keys detected in codebase.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
