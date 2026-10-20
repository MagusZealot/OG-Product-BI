#!/usr/bin/env py
"""
Verification script for T02: Data Safety Warning Callout.
Checks all acceptance criteria from GitHub issue #32.
"""

import re
import sys
from pathlib import Path

WORKSPACE_MAP = Path(__file__).parent.parent / "workspace_map.md"


def read_file():
    return WORKSPACE_MAP.read_text(encoding="utf-8")


def check_warning_callout(content):
    """Check for visual callout with ⚠️ emoji."""
    # Check for ⚠️ in the data safety section
    if "⚠️" not in content:
        return False, "Missing ⚠️ emoji in warning callout"
    
    # Check it's in a prominent position (near the top, in a heading or blockquote)
    lines = content.split("\n")
    for i, line in enumerate(lines[:50]):  # Check first 50 lines
        if "⚠️" in line and ("CRITICAL" in line or "WARNING" in line or "DATA SAFETY" in line):
            return True, f"Found warning callout at line {i+1}: {line.strip()}"
    
    return False, "⚠️ found but not in a prominent warning heading"


def check_constraint_table(content):
    """Check for table with 5 constraint rows."""
    # Find the FIRST table after the warning heading (constraint table, not details table)
    table_pattern = r"\| Constraint \| Details \|"
    match = re.search(table_pattern, content)
    if not match:
        return False, "Constraint table header not found"
    
    # Count data rows in the FIRST table only (before <details>)
    table_start = match.start()
    details_start = content.find("<details>", table_start)
    if details_start == -1:
        details_start = table_start + 2000
    
    table_section = content[table_start:details_start]
    
    rows = []
    for line in table_section.split("\n"):
        # Handle both regular table rows and blockquote-prefixed rows (> |)
        stripped = line.lstrip("> ").strip()
        if stripped.startswith("|") and "Constraint" not in stripped and "---" not in stripped and "Details" not in stripped:
            rows.append(stripped)
    
    if len(rows) != 5:
        return False, f"Expected 5 constraint rows, found {len(rows)}: {rows}"
    
    # Verify the 5 expected constraints
    expected_keywords = [
        "dataset size",
        "file sizes", 
        "ai restriction",
        "large files",
        "inspection"
    ]
    
    found_keywords = []
    for row in rows:
        for kw in expected_keywords:
            if kw.lower() in row.lower():
                found_keywords.append(kw)
                break
    
    if set(found_keywords) != set(expected_keywords):
        return False, f"Missing expected constraints. Found: {found_keywords}, Expected: {expected_keywords}"
    
    return True, f"Found 5 constraint rows: {found_keywords}"


def check_collapsible_details(content):
    """Check for collapsible <details> block with 11 large files."""
    # Check for <details> tag
    if "<details>" not in content:
        return False, "Missing <details> tag"
    
    if "</details>" not in content:
        return False, "Missing closing </details> tag"
    
    # Extract the details block
    details_start = content.find("<details>")
    details_end = content.find("</details>") + len("</details>")
    details_block = content[details_start:details_end]
    
    # Check for summary with "DO NOT READ" or similar
    if "DO NOT READ" not in details_block and "name-only" not in details_block.lower():
        return False, "Details summary missing 'DO NOT READ' or 'name-only' warning"
    
    # Count file rows in the table inside details
    file_rows = []
    for line in details_block.split("\n"):
        stripped = line.lstrip("> ").strip()
        if stripped.startswith("|") and ("data\\" in stripped or "legacy" in stripped or "output\\" in stripped):
            if "Path" not in stripped and "---" not in stripped:
                file_rows.append(stripped)
    
    if len(file_rows) != 11:
        return False, f"Expected 11 large files in details block, found {len(file_rows)}"
    
    # Verify each row has Path, Description, Size columns
    for row in file_rows:
        parts = [p.strip() for p in row.split("|")]
        if len(parts) < 4:  # | Path | Description | Size |
            return False, f"Row missing columns: {row}"
    
    return True, f"Found collapsible details block with {len(file_rows)} large files"


def check_never_statement(content):
    """Check for clear NEVER statement."""
    # Look for NEVER in the context of AI restriction
    never_patterns = [
        r"NEVER.*open.*read.*scan.*process",
        r"AI.*restriction.*NEVER",
        r"must NEVER",
        r"AI must NEVER",
    ]
    
    for pattern in never_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True, f"Found NEVER statement matching: {pattern}"
    
    # Fallback: just check NEVER appears in the constraint table
    if "NEVER" in content:
        return True, "Found NEVER in content"
    
    return False, "Missing NEVER statement about AI restrictions"


def check_rendering_prominence(content):
    """Check that the warning renders prominently (at top of document)."""
    lines = content.split("\n")
    
    # Find the data safety section
    safety_line = -1
    for i, line in enumerate(lines):
        if "CRITICAL DATA SAFETY WARNING" in line or "⚠️" in line:
            safety_line = i
            break
    
    if safety_line == -1:
        return False, "Data safety section not found"
    
    # Should be very early in the document (before TOC)
    toc_line = -1
    for i, line in enumerate(lines):
        if "Table of Contents" in line:
            toc_line = i
            break
    
    if toc_line != -1 and safety_line > toc_line:
        return False, f"Data safety section (line {safety_line+1}) appears after TOC (line {toc_line+1})"
    
    # Should be in first ~20 lines
    if safety_line > 20:
        return False, f"Data safety section too far down (line {safety_line+1}), should be near top"
    
    return True, f"Data safety section prominently placed at line {safety_line+1}"


def main():
    content = read_file()
    
    checks = [
        ("Warning callout with warning emoji", check_warning_callout),
        ("5-constraint table", check_constraint_table),
        ("Collapsible <details> with 11 files", check_collapsible_details),
        ("NEVER statement", check_never_statement),
        ("Prominent rendering", check_rendering_prominence),
    ]
    
    all_passed = True
    for name, check_fn in checks:
        passed, msg = check_fn(content)
        status = "PASS" if passed else "FAIL"
        # Sanitize message for Windows console
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(f"[{status}] {name}: {safe_msg}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All acceptance criteria PASSED")
        return 0
    else:
        print("Some acceptance criteria FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())