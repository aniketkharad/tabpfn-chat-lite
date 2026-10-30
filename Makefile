.PHONY: contract-check test gateway-test frontend-build size-check screenshots secret-scan verify

contract-check:
	@uv run python contract/check.py

test:
	@uv run pytest

gateway-test:
	@cd gateway && PATH=$$HOME/.bun/bin:$$PATH bun run test

frontend-build:
	@mkdir -p frontend/public/demo && cp demo/*.json frontend/public/demo/
	@cd frontend && PATH=$$HOME/.bun/bin:$$PATH bun run build

size-check: frontend-build
	@uv run python scripts/size-check.py

screenshots: frontend-build
	@uv run python scripts/render_capability_preview.py

# Offline drills never call upstream APIs; Settings just needs the variables to exist.
security-test load-test key-drills: export GEMINI_API_KEY ?= test-placeholder-not-a-real-key
security-test load-test key-drills: export TABPFN_TOKEN ?= test-placeholder-not-a-real-token

secret-scan:
	@uv run python scripts/secret-scan.py

security-test:
	@uv run python scripts/run_security_suite.py

load-test:
	@uv run python scripts/run_load_test.py

key-drills:
	@uv run python scripts/test_key_drills.py

verify: contract-check test gateway-test size-check secret-scan security-test load-test key-drills

