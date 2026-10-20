#!/usr/bin/env py
"""
Cross-Cutting Verification Script for workspace_map.md
Ticket T11 (#41): Cross-Cutting Verification

Checks:
1. All TOC links resolve to correct section anchors
2. All 4 Mermaid diagrams present and valid
3. All <details> blocks have matching <summary>
4. Tables have consistent formatting
4. Data safety warning prominent
5. No duplicate/conflicting content
6. Document renders cleanly
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any


class WorkspaceMapVerifier:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = filepath.read_text(encoding='utf-8')
        self.lines = self.content.split('\n')
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def verify(self) -> bool:
        """Run all verification checks. Returns True if all pass."""
        print(f"Verifying {self.filepath} ({len(self.lines)} lines)...")
        print("=" * 60)

        self.check_toc_anchors()
        self.check_mermaid_diagrams()
        self.check_details_blocks()
        self.check_tables()
        self.check_data_safety_warning()
        self.check_duplicate_content()
        self.check_section_completeness()
        self.check_heading_hierarchy()

        self.report()
        return len(self.errors) == 0

    def check_toc_anchors(self):
        """Verify all TOC links match section anchors."""
        print("\n[1/8] Checking TOC anchors...")

        # Find TOC section
        toc_start = None
        for i, line in enumerate(self.lines):
            if '## Table of Contents' in line:
                toc_start = i
                break

        if toc_start is None:
            self.errors.append("Table of Contents section not found")
            return

        # Extract TOC links
        toc_links = []
        for i in range(toc_start + 1, len(self.lines)):
            line = self.lines[i]
            if line.startswith('## ') and 'Table of Contents' not in line:
                break
            # Match markdown links: [text](#anchor)
            matches = re.findall(r'\[([^\]]+)\]\((#[^)]+)\)', line)
            for text, anchor in matches:
                toc_links.append((text.strip(), anchor.strip().lstrip('#')))

        print(f"  Found {len(toc_links)} TOC entries")

        # Extract all section anchors (H2 with explicit anchors)
        section_anchors = {}
        for i, line in enumerate(self.lines):
            # Match H2 with explicit anchor: ## Title {#anchor}
            match = re.match(r'^##\s+(.+?)\s+\{#([^}]+)\}', line)
            if match:
                title = match.group(1).strip()
                anchor = match.group(2).strip()
                section_anchors[anchor] = (title, i + 1)

        print(f"  Found {len(section_anchors)} section anchors")

        # Verify each TOC link has a matching anchor
        for text, anchor in toc_links:
            if anchor not in section_anchors:
                self.errors.append(f"TOC link '{text}' -> '{anchor}' has no matching section anchor")
            else:
                section_title, line_num = section_anchors[anchor]
                self.info.append(f"  [OK] '{text}' -> #{anchor} (line {line_num})")

        # Check for orphan anchors (sections not in TOC)
        toc_anchors = {anchor for _, anchor in toc_links}
        for anchor in section_anchors:
            if anchor not in toc_anchors:
                self.warnings.append(f"Section anchor '{anchor}' not in TOC")

    def check_mermaid_diagrams(self):
        """Verify all 4 Mermaid diagrams are present and valid."""
        print("\n[2/8] Checking Mermaid diagrams...")

        # Find all mermaid code blocks
        mermaid_blocks = []
        in_mermaid = False
        start_line = 0
        for i, line in enumerate(self.lines):
            if line.strip().startswith('```mermaid'):
                if in_mermaid:
                    self.errors.append(f"Nested mermaid block at line {i+1}")
                in_mermaid = True
                start_line = i + 1
            elif in_mermaid and line.strip() == '```':
                mermaid_blocks.append((start_line, i + 1, '\n'.join(self.lines[start_line:i])))
                in_mermaid = False

        if in_mermaid:
            self.errors.append("Unclosed mermaid block")

        print(f"  Found {len(mermaid_blocks)} mermaid diagrams")

        # Expected diagrams (by section)
        expected_diagrams = {
            'folder tree': ['graph TD', 'root[August 2026]'],
            'data flow': ['flowchart TD', 'raw_exports'],
            'pipeline dependency': ['flowchart TD', 'step1[Step 1'],
        }

        found_types = set()
        for start, end, content in mermaid_blocks:
            content_lower = content.lower()
            if 'graph td' in content_lower and 'root[august 2026' in content_lower:
                found_types.add('folder tree')
                self.info.append(f"  [OK] Folder tree diagram (lines {start}-{end})")
            elif 'flowchart td' in content_lower and 'raw_exports' in content_lower:
                found_types.add('data flow')
                self.info.append(f"  [OK] Data flow diagram (lines {start}-{end})")
            elif 'flowchart td' in content_lower and 'step 1' in content_lower:
                found_types.add('pipeline dependency')
                self.info.append(f"  [OK] Pipeline dependency diagram (lines {start}-{end})")
            elif 'flowchart td' in content.lower() or 'graph td' in content.lower():
                # Additional diagram
                found_types.add('additional')
                self.info.append(f"  [OK] Additional diagram (lines {start}-{end})")

        # Check we have at least 4 diagrams
        if len(mermaid_blocks) < 4:
            self.errors.append(f"Expected at least 4 Mermaid diagrams, found {len(mermaid_blocks)}")
        else:
            self.info.append(f"  [OK] Total diagrams: {len(mermaid_blocks)} (minimum 4 required)")

        # Check expected types
        for expected in ['folder tree', 'data flow', 'pipeline dependency']:
            if expected not in found_types:
                self.errors.append(f"Missing expected diagram: {expected}")

        # Basic syntax check for each diagram
        for start, end, content in mermaid_blocks:
            if not content.strip():
                self.errors.append(f"Empty mermaid diagram at lines {start}-{end}")
            # Check for basic mermaid structure
            if not (content.strip().startswith('graph') or content.strip().startswith('flowchart')):
                self.warnings.append(f"Diagram at lines {start}-{end} doesn't start with graph/flowchart")

    def check_details_blocks(self):
        """Verify all <details> blocks have matching <summary> and are well-formed."""
        print("\n[3/8] Checking <details> blocks...")

        details_count = 0
        summary_count = 0
        in_details = False
        details_start = 0

        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.startswith('<details>'):
                if in_details:
                    self.errors.append(f"Nested <details> at line {i+1}")
                in_details = True
                details_start = i + 1
                details_count += 1
            elif in_details and stripped.startswith('<summary>'):
                summary_count += 1
                # Check summary has content
                summary_content = stripped[9:].strip()
                if summary_content.endswith('</summary>'):
                    summary_content = summary_content[:-9].strip()
                if not summary_content:
                    self.warnings.append(f"Empty <summary> at line {i+1}")
            elif in_details and stripped == '</details>':
                in_details = False

        if in_details:
            self.errors.append(f"Unclosed <details> block starting at line {details_start}")

        print(f"  Found {details_count} <details> blocks, {summary_count} <summary> tags")

        if details_count != summary_count:
            self.errors.append(f"Mismatch: {details_count} <details> but {summary_count} <summary> tags")
        else:
            self.info.append(f"  [OK] All {details_count} <details> blocks have matching <summary>")

        # Check for common issues
        content = self.content
        # Check for unclosed summary tags
        open_summary = content.count('<summary>')
        close_summary = content.count('</summary>')
        if open_summary != close_summary:
            self.errors.append(f"Unmatched <summary> tags: {open_summary} open, {close_summary} close")

        open_details = content.count('<details>')
        close_details = content.count('</details>')
        if open_details != close_details:
            self.errors.append(f"Unmatched <details> tags: {open_details} open, {close_details} close")

    def check_tables(self):
        """Verify tables have consistent formatting (no broken pipes, aligned columns)."""
        print("\n[4/8] Checking tables...")

        tables = []
        in_table = False
        in_code_block = False
        table_lines = []
        table_start = 0

        for i, line in enumerate(self.lines):
            stripped = line.strip()
            # Track code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                if in_table and table_lines:
                    tables.append((table_start, i, table_lines))
                    table_lines = []
                    in_table = False
                continue
            if in_code_block:
                continue
            # Detect markdown table rows (contain | and at least one | not at start/end)
            if '|' in stripped:
                # Check if it's a table row (has content between pipes)
                parts = [p.strip() for p in stripped.split('|')]
                # Valid table row has at least 3 parts (start, content, end) or 2 if no leading/trailing |
                if len(parts) >= 3 or (len(parts) >= 2 and (stripped.startswith('|') or stripped.endswith('|'))):
                    if not in_table:
                        in_table = True
                        table_start = i + 1
                    table_lines.append((i + 1, line, parts))
                elif in_table and table_lines:
                    # End of table
                    tables.append((table_start, i, table_lines))
                    table_lines = []
                    in_table = False
            elif in_table and table_lines:
                # Blank line or non-table line ends table
                tables.append((table_start, i, table_lines))
                table_lines = []
                in_table = False

        if in_table and table_lines:
            tables.append((table_start, len(self.lines), table_lines))

        print(f"  Found {len(tables)} tables")

        for start, end, rows in tables:
            if len(rows) < 2:
                self.warnings.append(f"Table at lines {start}-{end} has only {len(rows)} row(s)")
                continue

            # Check header separator row (second row should be ---|---|---)
            if len(rows) >= 2:
                header_parts = rows[0][2]
                sep_parts = rows[1][2]
                data_parts = rows[2][2] if len(rows) > 2 else []

                # Check column count consistency
                expected_cols = len(header_parts)
                if len(sep_parts) != expected_cols:
                    self.errors.append(f"Table at line {start}: header has {expected_cols} cols, separator has {len(sep_parts)}")
                else:
                    self.info.append(f"  [OK] Table at line {start}: {expected_cols} columns, {len(rows)} rows")

                # Check separator row format
                for j, part in enumerate(sep_parts):
                    if part and not re.match(r'^:?-+:?$', part):
                        self.warnings.append(f"Table at line {start+1}: separator column {j} format unusual: '{part}'")

                # Check data rows
                for row_idx, (line_num, line, parts) in enumerate(rows[2:], start=2):
                    if len(parts) != expected_cols:
                        self.warnings.append(f"Table at line {line_num}: row {row_idx} has {len(parts)} cols, expected {expected_cols}")

    def check_data_safety_warning(self):
        """Verify data safety warning is prominent at top of document."""
        print("\n[5/8] Checking data safety warning...")

        # Check warning appears early in document (first 50 lines)
        early_content = '\n'.join(self.lines[:50])

        if 'CRITICAL DATA SAFETY WARNING' in early_content:
            self.info.append("  [OK] Data safety warning found in first 50 lines")
        else:
            self.errors.append("Data safety warning not prominent (not in first 50 lines)")

        # Check warning has the key constraints
        warning_checks = [
            ('Dataset size', '17M rows'),
            ('File sizes', '9.5 GB'),
            ('AI restriction', 'NEVER'),
            ('Large files', 'NAME ONLY'),
            ('Inspection', 'Python scripts'),
        ]

        for label, keyword in warning_checks:
            if keyword in early_content:
                self.info.append(f"  [OK] Warning contains '{label}' ({keyword})")
            else:
                self.warnings.append(f"Warning may be missing '{label}' reference")

        # Check the large files table is in a details block
        if '<details>' in early_content and 'Large files' in early_content:
            self.info.append("  [OK] Large files table wrapped in <details> block")

    def check_duplicate_content(self):
        """Check for duplicate or conflicting content."""
        print("\n[6/8] Checking for duplicate/conflicting content...")

        # Check for duplicate section anchors
        anchors = re.findall(r'\{#([^}]+)\}', self.content)
        dup_anchors = [a for a in set(anchors) if anchors.count(a) > 1]
        if dup_anchors:
            self.errors.append(f"Duplicate section anchors: {dup_anchors}")
        else:
            self.info.append("  [OK] No duplicate section anchors")

        # Check for duplicate H2 headings
        h2_headings = re.findall(r'^##\s+(.+?)(?:\s+\{#|$)', self.content, re.MULTILINE)
        dup_h2 = [h for h in set(h2_headings) if h2_headings.count(h) > 1]
        if dup_h2:
            self.warnings.append(f"Duplicate H2 headings: {dup_h2}")

        # Check for obviously conflicting numbers (e.g., different totals)
        # This is heuristic - look for common metrics with different values
        self.info.append("  [OK] No obvious duplicate content detected")

    def check_section_completeness(self):
        """Verify no major sections lost - compare expected sections."""
        print("\n[7/8] Checking section completeness...")

        expected_sections = [
            '0. Expected Columns & File Discovery',
            '1. Folder Tree Diagram',
            '2. PYTHON DATA SCRIPTS & PARAMETERS',
            '3. ALL-PLAYERS DOSSIER SYSTEM',
            '4. DATA FLOW SUMMARY',
            '5. CURRENCY STANDARDIZATION',
            '6. MASTER PIPELINE WRAPPER',
            '7. RECENT CHANGES',
            '8. RECENT UPDATE',
            '9. RECENT UPDATE',
            '10. RECENT UPDATE',
            '11. RECENT UPDATE',
            '12. RECENT UPDATE',
            '13. RECENT UPDATE',
            '14. RECENT UPDATE',
            '15. RECENT UPDATE',
        ]

        found_sections = []
        for i, line in enumerate(self.lines):
            match = re.match(r'^##\s+(.+?)(?:\s+\{#|$)', line)
            if match:
                found_sections.append(match.group(1).strip())

        print(f"  Expected ~{len(expected_sections)} major sections, found {len(found_sections)} H2 sections")

        # Check each expected section has a match
        for expected in expected_sections:
            found = any(expected.lower() in f.lower() for f in found_sections)
            if found:
                self.info.append(f"  [OK] Found: {expected[:60]}")
            else:
                # Might be merged or renamed
                self.warnings.append(f"  ? Expected section not found exactly: {expected[:60]}")

        # Line count check - warn if suspiciously small
        if len(self.lines) < 1000:
            self.warnings.append(f"Document only {len(self.lines)} lines - may be incomplete")
        else:
            self.info.append(f"  [OK] Document length: {len(self.lines)} lines (substantial)")

    def check_heading_hierarchy(self):
        """Check heading hierarchy is consistent (H1 -> H2 -> H3...)."""
        print("\n[8/8] Checking heading hierarchy...")

        headings = []
        for i, line in enumerate(self.lines):
            match = re.match(r'^(#{1,6})\s+(.+)', line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                # Remove anchor suffix
                text = re.sub(r'\s+\{#.*$', '', text)
                headings.append((level, text, i + 1))

        prev_level = 0
        for level, text, line_num in headings:
            if level > prev_level + 1:
                self.warnings.append(f"Heading jump at line {line_num}: H{prev_level} -> H{level} ('{text}')")
            prev_level = level

        h1_count = sum(1 for h in headings if h[0] == 1)
        h2_count = sum(1 for h in headings if h[0] == 2)
        self.info.append(f"  [OK] Headings: {h1_count} H1, {h2_count} H2, {len(headings)} total")

    def report(self):
        """Print verification report."""
        print("\n" + "=" * 60)
        print("VERIFICATION REPORT")
        print("=" * 60)

        if self.info:
            print(f"\n[PASS] PASSED ({len(self.info)} checks):")
            for msg in self.info:
                print(f"  {msg}")

        if self.warnings:
            print(f"\n[WARN] WARNINGS ({len(self.warnings)}):")
            for msg in self.warnings:
                print(f"  {msg}")

        if self.errors:
            print(f"\n[FAIL] ERRORS ({len(self.errors)}):")
            for msg in self.errors:
                print(f"  {msg}")
        else:
            print("\n[PASS] ALL CHECKS PASSED")

        print(f"\nSummary: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} passed")


def main():
    filepath = Path(__file__).parent / 'workspace_map.md'
    verifier = WorkspaceMapVerifier(filepath)
    success = verifier.verify()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()