#!/usr/bin/env python3
"""Size-check script: enforces bundle size budgets on frontend static SPA."""

import gzip
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"

INITIAL_BUDGET_BYTES = 50 * 1024  # 50 KB gzipped
CHART_BUDGET_BYTES = 15 * 1024    # 15 KB gzipped


def get_gzip_size(path: Path) -> int:
    with open(path, "rb") as f:
        data = f.read()
    return len(gzip.compress(data, compresslevel=9))


def main() -> int:
    if not DIST_DIR.exists() or not ASSETS_DIR.exists():
        print(f"Error: Build output directory not found at {DIST_DIR}")
        print("Run 'bun run build' inside frontend/ first.")
        return 1

    index_html = DIST_DIR / "index.html"
    if not index_html.exists():
        print(f"Error: index.html not found at {index_html}")
        return 1

    html_content = index_html.read_text(encoding="utf-8")

    # Find initial entry assets from index.html
    # Matches href="/assets/..." and src="/assets/..."
    entry_asset_names = set(re.findall(r'(?:href|src)="/assets/([^"]+)"', html_content))

    initial_js_css_bytes = 0
    chart_kit_bytes = 0

    print("=" * 64)
    print("FRONTEND BUNDLE BUDGET AUDIT")
    print("=" * 64)
    print(f"{'Asset':<35} {'Raw':>9} {'Gzip':>9} {'Type':<10}")
    print("-" * 64)

    for asset_path in sorted(ASSETS_DIR.iterdir()):
        if asset_path.is_file():
            raw_len = asset_path.stat().st_size
            gz_len = get_gzip_size(asset_path)
            name = asset_path.name

            is_initial = name in entry_asset_names or name.startswith("index-")
            is_chart = "ChartDispatcher" in name

            asset_type = "initial" if is_initial else ("chart" if is_chart else "lazy")
            if is_initial:
                initial_js_css_bytes += gz_len
            elif is_chart:
                chart_kit_bytes += gz_len

            print(f"{name:<35} {raw_len/1024:>8.2f}KB {gz_len/1024:>8.2f}KB {asset_type:<10}")

    print("=" * 64)
    print("BUDGET VERIFICATION:")
    print("-" * 64)

    initial_kb = initial_js_css_bytes / 1024
    initial_budget_kb = INITIAL_BUDGET_BYTES / 1024
    initial_passed = initial_js_css_bytes <= INITIAL_BUDGET_BYTES

    print(
        f"Initial JS+CSS:  {initial_kb:6.2f} KB / {initial_budget_kb:.1f} KB budget  "
        f"[{'PASS' if initial_passed else 'FAIL'}]"
    )

    chart_kb = chart_kit_bytes / 1024
    chart_budget_kb = CHART_BUDGET_BYTES / 1024
    chart_passed = chart_kit_bytes <= CHART_BUDGET_BYTES

    print(
        f"Lazy Chart Kit:  {chart_kb:6.2f} KB / {chart_budget_kb:.1f} KB budget  "
        f"[{'PASS' if chart_passed else 'FAIL'}]"
    )
    print("=" * 64)

    worker_dist = ROOT_DIR / "gateway" / "dist" / "index.js"
    if worker_dist.exists():
        worker_bytes = get_gzip_size(worker_dist)
        worker_kb = worker_bytes / 1024
        worker_budget_kb = 100.0  # 100 KB budget
        worker_passed = worker_bytes <= (100 * 1024)
        print(
            f"Worker Bundle:   {worker_kb:6.2f} KB / {worker_budget_kb:.1f} KB budget  "
            f"[{'PASS' if worker_passed else 'FAIL'}]"
        )
        print("=" * 64)
        if not worker_passed:
            print(f"FAILED: Worker bundle exceeds {worker_budget_kb} KB limit by {(worker_kb - worker_budget_kb):.2f} KB")
            return 1

    print("✓ ALL SIZE BUDGETS MET!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
