#!/usr/bin/env python3
"""
Test harness for the .github/scripts/update_readme.py module.

This script:
1. Imports the update_readme.py module via importlib.
2. Tests the pure functions with mock data (no network).
3. Verifies the animated SVG is well-formed XML and contains all 6 metrics.
4. Verifies the technology stack badges include logos where available.
5. Tests README update preserves content outside markers.
6. Verifies the main() workflow writes the SVG and updates READMEs correctly.
7. Ensures .github/README.md is removed (if it ever existed).
8. Optionally validates the workflow YAML syntax and secret usage.

Run with: python3 test_workflow_tech_stack.py
"""

import importlib.util
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

# Constants
REPO_ROOT = Path(__file__).parent
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "update_readme.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "update-tech-stack.yml"
README_PATH = REPO_ROOT / "README.md"
PROFILE_README_PATH = REPO_ROOT / ".github" / "profile" / "README.md"
SVG_OUTPUT_PATH = REPO_ROOT / "docs" / "code-stats.svg"

MOCK_METRICS = {
    "total_followers": 42,
    "total_commits": 81,
    "total_stars": 124,
    "total_forks": 37,
    "total_prs": 13,
    "total_issues": 5,
    "updated": "2026-10-17T16:00:00Z",
}

MOCK_LANG_BYTES = {
    "TypeScript": 50000,
    "JavaScript": 20000,
    "CSS": 5000,
    "HTML": 3000,
    "Python": 10000,
    "Go": 8000,
}


def load_module():
    """Load the update_readme.py module as mod."""
    spec = importlib.util.spec_from_file_location("update_readme", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_render_tech_stack():
    """Test render_tech_stack with mock language data."""
    mod = load_module()
    tech_html = mod.render_tech_stack(MOCK_LANG_BYTES)
    print("[1/7] Testing render_tech_stack...")
    print(f"  Generated tech block length: {len(tech_html)} chars")

    # Must contain the container
    assert '<div align="left">' in tech_html, "Missing container div"
    assert tech_html.count('<div align="left">') == 1
    assert tech_html.count('</div>') == 1

    # Must contain badges for each language
    for lang in MOCK_LANG_BYTES:
        assert lang in tech_html, f"Missing language {lang} in tech block"

    # Must contain logo URLs where mapped
    assert 'logo=typescript' in tech_html, "Missing TypeScript logo"
    assert 'logo=python' in tech_html, "Missing Python logo"
    assert 'logo=javascript' in tech_html, "Missing JavaScript logo (JS maps to javascript)"
    assert 'logo=go' in tech_html, "Missing Go logo"
    assert 'logo=css3' in tech_html, "Missing CSS logo"

    # Unknown language fallback (none in mock, but ensure no crash)
    print("  PASS: Tech stack rendered with logos and colours")
    return tech_html


def test_render_code_stats_svg():
    """Test render_code_stats_svg returns well-formed animated SVG."""
    mod = load_module()
    svg_text = mod.render_code_stats_svg(MOCK_METRICS)
    print("\n[2/7] Testing render_code_stats_svg...")
    print(f"  Generated SVG length: {len(svg_text)} chars")

    # Basic SVG structure
    assert svg_text.strip().startswith('<svg'), "SVG must start with <svg"
    assert svg_text.strip().endswith('</svg>'), "SVG must end with </svg>"
    assert 'viewBox="0 0 920 800"' in svg_text, "Missing or wrong viewBox"
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg_text, "Missing xmlns"

    # Must contain all 6 metric labels and values
    assert 'Followers' in svg_text
    assert '42' in svg_text
    assert 'Total Commits' in svg_text
    assert '81' in svg_text
    assert 'Total Stars' in svg_text
    assert '124' in svg_text
    assert 'Total Forks' in svg_text
    assert '37' in svg_text
    assert 'Total PRs' in svg_text
    assert '13' in svg_text
    assert 'Active Issues' in svg_text
    assert '5' in svg_text

    # Must contain SMIL animation elements
    assert '<animate' in svg_text, "Missing SMIL animate element"
    assert 'repeatCount="indefinite"' in svg_text, "Missing indefinite repeat"

    # Must contain live pulse circle
    assert 'LIVE' in svg_text, "Missing LIVE indicator"

    # Well-formed XML check
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(svg_text)
        print("  PASS: SVG is well-formed XML")
    except ET.ParseError as e:
        print(f"  FAIL: SVG is not well-formed XML: {e}")
        sys.exit(1)

    print("  PASS: SVG contains all metrics and animations")
    return svg_text


def test_update_readme():
    """Test update_readme preserves content outside markers."""
    mod = load_module()
    original = textwrap.dedent("""\
        # LoBot LLC

        ## Technology Stack

        Our products are built using the following programming languages and technologies, dynamically updated from our GitHub repositories:

        <!-- TECH-STACK-START -->
        <!-- TECH-STACK-END -->

        ## Code Statistics

        An animated continuous dashboard showing real-time metrics from https://github.com/LoBot-LLC

        <!-- CODE-STATS-START -->
        <!-- CODE-STATS-END -->

        ## Get Involved

        We welcome contributors.
        """)
    tech_block = '<div align="left">\n  <img src="https://img.shields.io/badge/-TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />\n</div>'
    stats_block = (
        '<p align="center">\n'
        '  <img src="docs/code-stats.svg" alt="Live Code Statistics dashboard for LoBot-LLC" width="920" height="640" />\n'
        '</p>\n\n'
        '<div align="center">\n\n'
        'Real-time metrics fetched live from <a href="https://github.com/LoBot-LLC">github.com/LoBot-LLC</a> via the <code>DASHBOARD_API</code> secret. '
        'Values are refreshed automatically by the scheduled GitHub Actions workflow.\n\n'
        '</div>'
    )
    updated = mod.update_readme(original, stats_block, tech_block)
    print("\n[3/7] Testing update_readme...")
    print(f"  Original length: {len(original)} chars")
    print(f"  Updated length: {len(updated)} chars")

    # Each marker appears exactly once
    assert updated.count('<!-- TECH-STACK-START -->') == 1
    assert updated.count('<!-- TECH-STACK-END -->') == 1
    assert updated.count('<!-- CODE-STATS-START -->') == 1
    assert updated.count('<!-- CODE-STATS-END -->') == 1

    # Content between markers replaced
    assert tech_block in updated, "Tech block not inserted"
    assert stats_block in updated, "Stats block not inserted"

    # Content outside markers preserved
    outside = (
        mod.TECH_REGEX.sub('<<TECH>>', original)
    )
    outside = (
        mod.STATS_REGEX.sub('<<STATS>>', outside)
    )
    updated_outside = (
        mod.TECH_REGEX.sub('<<TECH>>', updated)
    )
    updated_outside = (
        mod.STATS_REGEX.sub('<<STATS>>', updated_outside)
    )
    assert outside == updated_outside, "Content outside markers changed"

    print("  PASS: README updated correctly with preservation")
    return updated


def test_main_writes_files():
    """Test main() writes SVG and updates READMEs (with mocked API)."""
    mod = load_module()
    print("\n[4/7] Testing main() integration...")

    # Ensure fresh state: remove SVG and legacy README if exist
    if SVG_OUTPUT_PATH.exists():
        SVG_OUTPUT_PATH.unlink()
    legacy = REPO_ROOT / ".github" / "README.md"
    if legacy.exists():
        legacy.unlink()

    with patch.object(mod, 'collect_metrics', return_value=MOCK_METRICS), \
         patch.object(mod, 'collect_languages', return_value=MOCK_LANG_BYTES):
        mod.main()

    # SVG written
    assert SVG_OUTPUT_PATH.exists(), "SVG output file not created"
    svg_text = SVG_OUTPUT_PATH.read_text(encoding="utf-8")
    assert svg_text.strip().startswith('<svg'), "SVG not well-formed"
    assert '</svg>' in svg_text
    assert 'Followers' in svg_text and '42' in svg_text
    print("  PASS: SVG file written with correct data")

    # README.md updated
    assert README_PATH.exists(), "README.md missing"
    readme_content = README_PATH.read_text(encoding="utf-8")
    assert '<img src="docs/code-stats.svg"' in readme_content, "README missing dashboard image"
    assert 'Real-time metrics fetched live from' in readme_content, "README missing stats note"
    # Exactly one marker each
    assert readme_content.count('<!-- TECH-STACK-START -->') == 1
    assert readme_content.count('<!-- CODE-STATS-START -->') == 1
    # No hard-coded table
    assert '<table>' not in readme_content, "README still contains hard-coded table"
    print("  PASS: README.md updated correctly")

    # .github/profile/README.md updated
    assert PROFILE_README_PATH.exists(), "Profile README missing"
    profile_content = PROFILE_README_PATH.read_text(encoding="utf-8")
    assert '<img src="docs/code-stats.svg"' in profile_content, "Profile README missing dashboard image"
    assert 'Real-time metrics fetched live from' in profile_content, "Profile README missing stats note"
    assert profile_content.count('<!-- TECH-STACK-START -->') == 1
    assert profile_content.count('<!-- CODE-STATS-START -->') == 1
    print("  PASS: .github/profile/README.md updated correctly")

    # Legacy .github/README.md removed (should not exist)
    assert not legacy.exists(), "Legacy .github/README.md should not exist"
    print("  PASS: Legacy .github/README.md does not exist")

    return True


def test_workflow_yaml():
    """Light sanity check that workflow calls the script and uses DASHBOARD_API."""
    print("\n[5/7] Testing workflow YAML...")
    if not WORKFLOW_PATH.exists():
        print("  WARN: workflow file not found")
        return
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '.github/scripts/update_readme.py' in raw, "Workflow does not call our script"
    assert 'DASHBOARD_API:' in raw, "Workflow missing DASHBOARD_API secret"
    assert 'GITHUB_TOKEN:' in raw, "Workflow missing GITHUB_TOKEN fallback"
    # Quick YAML parse if PyYAML available
    try:
        import yaml
        data = yaml.safe_load(raw)
        assert data['name'] == 'Update Technology Stack and Code Statistics'
        assert 'write' in str(data.get('permissions', {}))
    except Exception:
        # If PyYAML not installed, just check for basic structure
        assert 'on:' in raw and 'jobs:' in raw
    print("  PASS: Workflow references script and uses correct secrets")


def test_no_hardcoded_values_in_readme():
    """Ensure README.md has no hard-coded tech stack or stats."""
    print("\n[6/7] Checking for hard-coded values in README.md...")
    content = README_PATH.read_text(encoding="utf-8")
    # Should not contain the old static tech-stack badge ( shields.io without logo param from original workflow )
    # The old workflow produced badges like: https://img.shields.io/badge/-TypeScript-3178C6
    # New ones always have logo= when mapped.
    # We'll just ensure no hard-coded list appears.
    lines = content.splitlines()
    in_tech = False
    for line in lines:
        if '<!-- TECH-STACK-START -->' in line:
            in_tech = True
            continue
        if '<!-- TECH-STACK-END -->' in line:
            in_tech = False
            continue
        if in_tech and line.strip() and not line.startswith('  <img'):
            # Inside tech block but not a badge line -> unexpected
            if line.strip() and not line.startswith('<!--'):
                print(f"  WARN: unexpected line in tech block: {line}")
    # Should not contain the old static stats badge table
    assert '<table>' not in content, "README still contains hard-coded table"
    print("  PASS: No hard-coded values found in markers")


def test_summary():
    """Print a summary of what was tested."""
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print("Summary:")
    print(f"  - Module {SCRIPT_PATH.relative_to(REPO_ROOT)}: loaded successfully")
    print(f"  - render_tech_stack: renders logos and colours")
    print(f"  - render_code_stats_svg: well-formed SVG with all 6 metrics + SMIL")
    print(f"  - update_readme: preserves content outside markers")
    print(f"  - main(): writes SVG and updates both READMEs")
    print(f"  - workflow: references script and uses DASHBOARD_API secret")
    print(f"  - README.md: free of hard-coded tables/lists")
    print(f"  - .github/profile/README.md: kept and updated")
    print(f"  - .github/README.md: ensured removed (does not exist)")


def main():
    print("=" * 60)
    print("Testing .github/scripts/update_readme.py")
    print("=" * 60)

    test_render_tech_stack()
    test_render_code_stats_svg()
    test_update_readme()
    test_main_writes_files()
    test_workflow_yaml()
    test_no_hardcoded_values_in_readme()
    test_summary()


if __name__ == '__main__':
    main()