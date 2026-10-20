#!/usr/bin/env py
"""
Verification script for Section 5 - Currency Standardization in workspace_map.md
Checks all acceptance criteria from ticket #38.
"""
import re
import sys

def verify_section_5():
    with open("workspace_map.md", "r", encoding="utf-8") as f:
        content = f.read()

    errors = []
    warnings = []

    # 1. Check section anchor present
    if "#5-currency-standardization" not in content:
        errors.append("Section anchor '#5-currency-standardization' not found")
    else:
        print("[OK] Section anchor '#5-currency-standardization' present")

    # 2. Check 19 currencies listed
    currencies = ["CNY", "IDR", "VND", "KRW", "JPY", "THB", "USD", "SGD", "HKD", 
                  "TWD", "MYR", "INR", "MMK", "NPR", "BDT", "TRY", "USDT", "IDRK", "VNDK"]
    
    # Find the section 5 content
    section_match = re.search(r'## 5\. CURRENCY STANDARDIZATION.*?(?=\n## |\Z)', content, re.DOTALL)
    if not section_match:
        errors.append("Section 5 not found")
        section_text = ""
    else:
        section_text = section_match.group(0)

    missing_currencies = []
    for curr in currencies:
        if curr not in section_text:
            missing_currencies.append(curr)
    
    if missing_currencies:
        errors.append(f"Missing currencies in Section 5: {', '.join(missing_currencies)}")
    else:
        print(f"[OK] All 19 currencies listed: {', '.join(currencies)}")

    # 3. Check currency_converter.py table with 6 rows (cache file, TTL, convert_to_php, get_country/CURRENCY_COUNTRY, rate fallback, unsupported currencies)
    converter_table_pattern = r'\|.*cache.*file.*\||\|.*TTL.*\||\|.*convert_to_php.*\||\|.*get_country.*\||\|.*CURRENCY_COUNTRY.*\||\|.*rate.*fallback.*\||\|.*unsupported.*currenc.*\|'
    converter_rows = re.findall(r'\|[^|]*cache[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*TTL[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*convert_to_php[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*get_country[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*CURRENCY_COUNTRY[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*rate.*fallback[^|]*\|[^|]*\|', section_text, re.IGNORECASE)
    converter_rows += re.findall(r'\|[^|]*unsupported.*currenc[^|]*\|[^|]*\|', section_text, re.IGNORECASE)

    # Better: check for a table with these 6 specific rows
    required_table_rows = [
        "cache file",
        "TTL",
        "convert_to_php",
        "get_country",
        "rate fallback",
        "unsupported"
    ]
    
    table_found = False
    table_row_count = 0
    for req in required_table_rows:
        if re.search(rf'\|[^|]*{re.escape(req)}[^|]*\|', section_text, re.IGNORECASE):
            table_row_count += 1
        else:
            errors.append(f"currency_converter.py table missing row for: {req}")
    
    if table_row_count >= 6:
        print(f"[OK] currency_converter.py table has all 6 required rows")
    else:
        errors.append(f"currency_converter.py table has only {table_row_count}/6 required rows")

    # 4. Check 8-script usage table present
    scripts = [
        "whale_tracking",
        "time_series_analysis",
        "chaser_detection",
        "operator_analysis",
        "build_all_players_dossiers",
        "generate_player_behavior_data",
        "generate_heatmap_matrix",
        "build_individual_dossiers"
    ]
    
    script_table_found = False
    script_matches = 0
    for script in scripts:
        if script in section_text:
            script_matches += 1
        else:
            errors.append(f"Script usage table missing: {script}.py")
    
    if script_matches >= 8:
        print(f"[OK] All 8 scripts referenced in usage table")
    else:
        errors.append(f"Only {script_matches}/8 scripts found in usage table")

    # 5. Check output impact statement
    impact_keywords = ["derived CSVs", "JSON files", "dashboards", "PHP-normalized"]
    impact_found = True
    for kw in impact_keywords:
        if kw.lower() not in section_text.lower():
            impact_found = False
            errors.append(f"Output impact statement missing keyword: {kw}")
    
    if impact_found:
        print("[OK] Output impact statement present with all required elements")
    else:
        pass  # errors already added

    # Summary
    if errors:
        print("\n[FAIL] VERIFICATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("\n[PASS] ALL VERIFICATION CHECKS PASSED")
        return True

if __name__ == "__main__":
    success = verify_section_5()
    sys.exit(0 if success else 1)