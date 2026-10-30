"""Shared pytest configuration.

The suite is offline-first and runs entirely against fakes. Settings still require
the two upstream credentials to be present, so supply obviously fake placeholders
when the environment does not already provide them. Real values (from `.env`) win.
"""

import os

os.environ.setdefault("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
os.environ.setdefault("TABPFN_TOKEN", "test-placeholder-not-a-real-token")
