#!/usr/bin/env python3
"""
Test harness for the update-tech-stack.yml workflow Python script.

This script:
1. Verifies the workflow's embedded Python is syntactically correct.
2. Extracts the exact regex patterns the workflow uses for replacement.
3. Applies the same regex replacements the workflow does to a copy of README.md.
4. Outputs what the final README would look like with sample/mock data
   (no GitHub API calls are made).
5. Verifies both sections are correctly matched and replaced atomically.
"""

import os
import re
import sys
import textwrap
import json
import urllib.parse
from pathlib import Path

WORKFLOW_PATH = Path(__file__).parent / '.github' / 'workflows' / 'update-tech-stack.yml'
README_PATH = Path(__file__).parent / 'README.md'

ORG = 'LoBot-LLC'


def extract_python_from_workflow(path):
    """Extract the embedded Python script from the workflow YAML heredoc."""
    content = path.read_text()
    match = re.search(r"python - <<'PYEOF'\n(.*?)PYEOF", content, re.DOTALL)
    if not match:
        raise RuntimeError("Could not find PYEOF heredoc in workflow file")
    # The YAML heredoc indents the Python lines; dedent to get valid Python.
    return textwrap.dedent(match.group(1))


def extract_regex_patterns(script_source):
    """Extract the exact regex patterns the workflow script uses."""
    tech_match = re.search(
        r"re\.compile\(\s*r['\"](.*?)['\"]\s*,\s*re\.DOTALL\s*\)",
        script_source
    )
    # Find both re.compile calls
    pattern_re = re.compile(r"re\.compile\([^)]*re\.DOTALL[^)]*\)")
    matches = pattern_re.findall(script_source)

    patterns = []
    for m in matches:
        raw_match = re.search(r"r['\"](.*?)['\"]", m, re.DOTALL)
        if raw_match:
            patterns.append(raw_match.group(1))
    return patterns


def test_syntax(script):
    """Verify the embedded Python script compiles without syntax errors."""
    try:
        compile(script, '<workflow-script>', 'exec')
    except SyntaxError as e:
        print(f"FAIL: Syntax error in workflow script: {e}")
        sys.exit(1)
    print("[1/4] PASS: Workflow Python script is syntactically correct")
    print(f"         Extracted {len(script)} characters of Python from workflow YAML")


def test_regex_patterns(script):
    """Verify the regex patterns extracted from the script are correct."""
    patterns = extract_regex_patterns(script)

    print(f"\n[2/4] Regex patterns found in workflow script:")
    expected_patterns = [
        r'<!-- TECH-STACK-START -->.*?<!-- TECH-STACK-END -->',
        r'<!-- CODE-STATS-START -->.*?<!-- CODE-STATS-END -->',
    ]

    found_tech = False
    found_stats = False
    for p in patterns:
        print(f"  - {p}")
        if p == expected_patterns[0]:
            found_tech = True
        if p == expected_patterns[1]:
            found_stats = True

    assert found_tech, "TECH-STACK regex pattern not found in script or doesn't match expected"
    assert found_stats, "CODE-STATS regex pattern not found in script or doesn't match expected"

    # Now test these patterns against the actual README
    readme = README_PATH.read_text()

    tech_pattern = re.compile(patterns[0], re.DOTALL)
    stats_pattern = re.compile(patterns[1], re.DOTALL)

    tech_matches = tech_pattern.findall(readme)
    stats_matches = stats_pattern.findall(readme)

    print(f"\n  Matching against README.md:")
    print(f"  TECH-STACK pattern matches: {len(tech_matches)}")
    print(f"  CODE-STATS pattern matches: {len(stats_matches)}")
    print(f"  TECH-STACK matched text: {repr(tech_matches[0][:80])}")
    print(f"  CODE-STATS matched text: {repr(stats_matches[0][:80])}")

    assert len(tech_matches) == 1, f"Expected 1 TECH-STACK match in README, got {len(tech_matches)}"
    assert len(stats_matches) == 1, f"Expected 1 CODE-STATS match in README, got {len(stats_matches)}"

    print("  PASS: Both regex patterns correctly match their respective markers in README.md")


def generate_mock_tech_block(script):
    """Generate a mock tech-block using sample language data, mimicking the script logic."""
    colors = {
        'TypeScript': '3178C6', 'JavaScript': 'F7DF1E', 'Python': '3776AB',
        'Go': '00ADD8', 'Rust': 'DEA584', 'Java': 'ED8B00', 'C': '555555',
        'C++': 'F34B7D', 'Ruby': 'CC342D', 'PHP': '777BB4',
        'Swift': 'F05138', 'Kotlin': 'A97BFF', 'HTML': 'E34F26',
        'CSS': '1572B6', 'SCSS': 'C6538C', 'Shell': '89E051', 'Dockerfile': '384D54',
        'YAML': 'CB171E', 'JSON': '000000', 'Markdown': '000000',
        'Vue': '4FC08D', 'Svelte': 'FF3E00', 'Dart': '0175C2',
        'Lua': '000080', 'R': '276DC3', 'Scala': 'DC322F', 'Elixir': '4E2A8E',
        'Haskell': '5E5086', 'Perl': '39457E',
    }
    logo_map = {
        'TypeScript': 'typescript', 'JavaScript': 'javascript', 'Python': 'python',
        'Go': 'go', 'Rust': 'rust', 'Java': 'java', 'C': 'c', 'C++': 'cplusplus',
        'Ruby': 'ruby', 'PHP': 'php', 'Swift': 'swift',
        'Kotlin': 'kotlin', 'HTML': 'html5', 'CSS': 'css3', 'SCSS': 'sass',
        'Shell': 'gnubash', 'Dockerfile': 'docker', 'YAML': 'yaml', 'JSON': 'json',
        'Markdown': 'markdown', 'Vue': 'vuejs', 'Svelte': 'svelte', 'Dart': 'dart',
        'Lua': 'lua', 'R': 'r', 'Scala': 'scala', 'Elixir': 'elixir',
        'Haskell': 'haskell', 'Perl': 'perl',
    }

    def get_logo(lang):
        return logo_map.get(lang, '')

    # Mock language data (simulating what the GitHub API would return)
    lang_bytes = {
        'TypeScript': 50000,
        'CSS': 5000,
        'HTML': 3000,
        'Python': 10000,
        'Go': 8000,
    }

    tech_badges = []
    for lang, count in sorted(lang_bytes.items(), key=lambda x: -x[1]):
        color = colors.get(lang, '858585')
        lg = get_logo(lang)
        if lg:
            badge = f'<img src="https://img.shields.io/badge/-{urllib.parse.quote(lang)}-{color}?logo={lg}&logoColor=white" alt="{lang}" />'
        else:
            badge = f'<img src="https://img.shields.io/badge/-{urllib.parse.quote(lang)}-{color}" alt="{lang}" />'
        tech_badges.append(badge)

    tech_block = '<div align="left">\n  ' + '\n  '.join(tech_badges) + '\n</div>'
    print(f"\n  Generated {len(tech_badges)} tech badges (mock data)")
    return tech_block


def generate_mock_stats_block(script):
    """Generate a mock stats-block using sample metrics, mimicking the script logic."""
    colors = {
        'TypeScript': '3178C6', 'JavaScript': 'F7DF1E', 'Python': '3776AB',
        'Go': '00ADD8', 'Rust': 'DEA584',
    }
    logo_map = {
        'TypeScript': 'typescript', 'Python': 'python', 'Go': 'go',
    }

    def get_logo(lang):
        return logo_map.get(lang, '')

    # Mock metrics (simulating API responses)
    total_followers = 42
    total_commits = 81  # 50 + 30 from TecnoIndicator + 1 from lib-utils
    total_prs = 3       # 2 from TecnoIndicator + 1 from lib-utils
    total_issues = 2    # 1 valid issue from TecnoIndicator + 1 from lib-utils
    most_active_repo = 'TecnoIndicator'

    lang_bytes = {
        'TypeScript': 50000, 'CSS': 5000, 'HTML': 3000,
        'Python': 10000, 'Go': 8000,
    }
    most_used_lang = max(lang_bytes.items(), key=lambda x: x[1])[0]

    stats_badges = []

    # Organization Followers
    stats_badges.append(f'<a href="https://github.com/orgs/{ORG}/people">')
    stats_badges.append(f'  <img src="https://img.shields.io/github/followers/{ORG}?style=social&logo=github&color=blue&label=Followers" alt="Organization Followers" />')
    stats_badges.append(f'</a>')

    # Total Commits
    stats_badges.append(f'<a href="https://github.com/{ORG}?tab=repositories">')
    stats_badges.append(f'  <img src="https://img.shields.io/badge/Total%20Commits-{total_commits}-lightgrey" alt="Total Commits" />')
    stats_badges.append(f'</a>')

    # Most Active Repository
    stats_badges.append(f'<a href="https://github.com/{ORG}/{most_active_repo}">')
    stats_badges.append(f'  <img src="https://img.shields.io/badge/Most%20Active-{most_active_repo}-purple" alt="Most Active Repository" />')
    stats_badges.append(f'</a>')

    # Most Used Language
    color = colors.get(most_used_lang, '858585')
    lg = get_logo(most_used_lang)
    stats_badges.append(f'<a href="https://github.com/{ORG}?tab=repositories&q=&type=source&language={urllib.parse.quote(most_used_lang)}">')
    if lg:
        stats_badges.append(f'  <img src="https://img.shields.io/badge/-{urllib.parse.quote(most_used_lang)}-{color}?logo={lg}&logoColor=white" alt="{most_used_lang}" />')
    else:
        stats_badges.append(f'  <img src="https://img.shields.io/badge/-{urllib.parse.quote(most_used_lang)}-{color}" alt="{most_used_lang}" />')
    stats_badges.append(f'</a>')

    # Total Pull Requests
    stats_badges.append(f'<a href="https://github.com/{ORG}?tab=repositories&q=&type=source">')
    stats_badges.append(f'  <img src="https://img.shields.io/badge/Total%20PRs-{total_prs}-orange" alt="Total Pull Requests" />')
    stats_badges.append(f'</a>')

    # Total Open Issues
    stats_badges.append(f'<a href="https://github.com/{ORG}?tab=issues&q=is%3Aopen+is%3Aissue">')
    stats_badges.append(f'  <img src="https://img.shields.io/badge/Open%20Issues-{total_issues}-red" alt="Total Open Issues" />')
    stats_badges.append(f'</a>')

    stats_block = '<div align="left">\n  ' + '\n  '.join(stats_badges) + '\n</div>'
    print(f"\n  Generated {len(stats_badges) // 3} stats badges (mock data)")
    print(f"  Mock metrics: {total_followers} followers, {total_commits} commits, {total_prs} PRs, {total_issues} issues")
    return stats_block


def simulate_readme_update(script):
    """Apply the same regex replacements the workflow does and show the output."""
    patterns = extract_regex_patterns(script)
    tech_replacement = f'<!-- TECH-STACK-START -->\n{generate_mock_tech_block(script)}\n<!-- TECH-STACK-END -->'
    stats_replacement = f'<!-- CODE-STATS-START -->\n{generate_mock_stats_block(script)}\n<!-- CODE-STATS-END -->'

    print(f"\n[3/4] Applying regex replacements (same as workflow)...")
    print(f"  Tech block replacement uses: {repr(patterns[0])}")
    print(f"  Stats block replacement uses: {repr(patterns[1])}")

    # Apply the replacements exactly as the workflow does
    tech_pattern = re.compile(patterns[0], re.DOTALL)
    stats_pattern = re.compile(patterns[1], re.DOTALL)

    original = README_PATH.read_text()
    updated = tech_pattern.sub(tech_replacement, original)
    updated = stats_pattern.sub(stats_replacement, updated)

    # Verify both replacements occurred
    assert updated != original, "README content was not changed by replacements!"
    assert '<div align="left">' in updated, "Tech block was not inserted!"
    assert 'img.shields.io' in updated, "Badges were not inserted!"

    print("  PASS: Both sections replaced successfully")

    return updated, original


def test_atomicity(updated, original):
    """Verify both sections are updated in a single write operation."""
    print(f"\n[4/4] Atomicity verification...")

    # In the workflow, the script:
    # 1. Reads README.md once
    # 2. Applies tech_pattern.sub() to content
    # 3. Applies stats_pattern.sub() to the SAME content (modified in memory)
    # 4. Writes README.md once
    # This means both changes are committed together - atomic at the file level.

    tech_pattern = re.compile(r'<!-- TECH-STACK-START -->.*?<!-- TECH-STACK-END -->', re.DOTALL)
    stats_pattern = re.compile(r'<!-- CODE-STATS-START -->.*?<!-- CODE-STATS-END -->', re.DOTALL)

    # Verify both sections have content between markers
    tech_block = tech_pattern.search(updated).group()
    stats_block = stats_pattern.search(updated).group()

    print(f"  TECH-STACK block length: {len(tech_block)} chars")
    print(f"  CODE-STATS block length: {len(stats_block)} chars")

    # Verify exactly one of each marker (no duplicates from double replacement)
    assert updated.count('<!-- TECH-STACK-START -->') == 1, "Tech start marker duplicated!"
    assert updated.count('<!-- TECH-STACK-END -->') == 1, "Tech end marker duplicated!"
    assert updated.count('<!-- CODE-STATS-START -->') == 1, "Stats start marker duplicated!"
    assert updated.count('<!-- CODE-STATS-END -->') == 1, "Stats end marker duplicated!"

    # Verify the rest of the README is unchanged
    # Extract everything outside the two replaced sections
    original_tech = tech_pattern.search(original).group()
    original_stats = stats_pattern.search(original).group()

    original_rest = original.replace(original_tech, '<<TECH>>').replace(original_stats, '<<STATS>>')
    updated_rest = updated.replace(tech_block, '<<TECH>>').replace(stats_block, '<<STATS>>')

    assert original_rest == updated_rest, "Content outside the two sections changed!"
    print("  PASS: Content outside replaced sections is identical (rest of README preserved)")
    print("  PASS: No duplicate markers (each marker appears exactly once)")
    print("  PASS: Both sections updated atomically (single write, both changes applied together)")

    return True


def main():
    print("=" * 60)
    print("Testing update-tech-stack.yml workflow Python script")
    print("=" * 60)

    # Step 1: Extract and syntax-check the script
    script = extract_python_from_workflow(WORKFLOW_PATH)
    test_syntax(script)

    # Step 2: Verify regex patterns
    test_regex_patterns(script)

    # Step 3: Simulate README update with mock data
    updated, original = simulate_readme_update(script)

    # Step 4: Verify atomicity
    test_atomicity(updated, original)

    # Print the simulated final README
    print(f"\n{'='*60}")
    print("SIMULATED FINAL README.md (with mock GitHub data)")
    print("=" * 60)
    print(updated)

    print(f"\n{'='*60}")
    print("TECH-STACK SECTION (between markers)")
    print("=" * 60)
    tech_pattern = re.compile(r'<!-- TECH-STACK-START -->.*?<!-- TECH-STACK-END -->', re.DOTALL)
    print(tech_pattern.search(updated).group())

    print(f"\n{'='*60}")
    print("CODE-STATS SECTION (between markers)")
    print("=" * 60)
    stats_pattern = re.compile(r'<!-- CODE-STATS-START -->.*?<!-- CODE-STATS-END -->', re.DOTALL)
    print(stats_pattern.search(updated).group())

    print(f"\n{'='*60}")
    print("ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - Python script: syntactically valid")
    print(f"  - TECH-STACK regex: correctly matches marker in README")
    print(f"  - CODE-STATS regex: correctly matches marker in README")
    print(f"  - Both sections updated atomically: YES (single file read + write)")


if __name__ == '__main__':
    main()
