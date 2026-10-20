#!/usr/bin/env python3
"""
Advanced Casino Data Analysis Tool - Optimized with Progress Tracking
"""
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break


import csv
import json
import sys
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime

# Add src/ingest to path for currency_converter import
sys.path.insert(0, str(Path(__file__).parent))
from currency_converter import convert_to_php, get_country, CURRENCY_COUNTRY

# Configuration
FOLDER = Path(WORKSPACE / "data" / "raw")
REPORT_DIR = Path(WORKSPACE / "output")
REPORT_DIR.mkdir(exist_ok=True)
PROGRESS_FILE = REPORT_DIR / "progress.json"


def update_progress(stage, message, progress=None, details=None):
    """Update progress file for dashboard"""
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage': stage,
        'message': message,
        'progress': progress,
        'details': details or {}
    }
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_all_csv_files():
    """Get all CSV files in the folder"""
    return sorted(FOLDER.glob("*.csv"))


def safe_float(val):
    """Safely convert string to float"""
    if not val:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def safe_int(val):
    """Safely convert string to int"""
    if not val:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


# ============================================================================
# 1. WHALE TRACKING (PARETO PRINCIPLE)
# ============================================================================

def analyze_whales():
    """
    Identify top 20% of players generating 80% of debit_amount
    Track their session lengths and behavior
    """
    update_progress('whale_tracking', 'Starting whale tracking analysis...', 0)
    
    player_debit = defaultdict(float)
    player_bets = defaultdict(int)
    player_sessions = defaultdict(list)
    player_countries = defaultdict(set)
    
    files = get_all_csv_files()
    update_progress('whale_tracking', f'Processing {len(files)} files for whale analysis...', 5, 
                    {'total_files': len(files), 'processed': 0})
    
    for file_idx, file_path in enumerate(files, 1):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    player_id = row.get('player_id', '').strip()
                    if not player_id:
                        continue
                    
                    debit = safe_float(row.get('debit_amount', 0))
                    currency = row.get('currency', '').strip()
                    timestamp_str = row.get('formatted_debit_at', '').strip()
                    
                    # Convert to PHP using date-relative rate
                    debit_php = convert_to_php(debit, currency, timestamp_str)
                    
                    country = get_country(currency)
                    
                    player_debit[player_id] += debit_php
                    player_bets[player_id] += 1
                    player_countries[player_id].add(country)
                    
                    if timestamp_str:
                        try:
                            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            player_sessions[player_id].append(ts)
                        except ValueError:
                            pass
                    
        except Exception as e:
            print(f"    Error: {e}")
            continue
        
        pct = 5 + int((file_idx / len(files)) * 40)
        update_progress('whale_tracking', f'Processing file {file_idx}/{len(files)}...', pct,
                        {'total_files': len(files), 'processed': file_idx})
    
    # Calculate Pareto distribution
    total_debit = sum(player_debit.values())
    sorted_players = sorted(player_debit.items(), key=lambda x: x[1], reverse=True)
    
    cumulative_debit = 0
    whale_count_80 = 0
    whale_threshold_80 = 0
    
    for idx, (player_id, debit) in enumerate(sorted_players, 1):
        cumulative_debit += debit
        cumulative_pct = (cumulative_debit / total_debit) * 100
        
        if cumulative_pct >= 80 and whale_count_80 == 0:
            whale_threshold_80 = debit
            whale_count_80 = idx
    
    # Identify whales
    whales = [(pid, debit) for pid, debit in sorted_players if debit >= whale_threshold_80]
    
    update_progress('whale_tracking', 'Analyzing whale behavior...', 50,
                    {'total_players': len(player_debit), 'whales': len(whales)})
    
    # Whale session analysis
    whale_sessions = []
    for player_id, debit in whales[:20]:
        sessions = player_sessions.get(player_id, [])
        if sessions:
            sessions_sorted = sorted(sessions)
            session_times = []
            for i in range(0, len(sessions_sorted) - 1, 2):
                if i + 1 < len(sessions_sorted):
                    duration = (sessions_sorted[i+1] - sessions_sorted[i]).total_seconds() / 3600
                    session_times.append(duration)
            
            avg_session = sum(session_times) / len(session_times) if session_times else 0
            countries = list(player_countries.get(player_id, ['Unknown']))
            
            whale_sessions.append({
                'player_id': player_id,
                'total_debit': debit,
                'total_bets': player_bets[player_id],
                'avg_session_hours': round(avg_session, 2),
                'session_count': len(sessions),
                'countries': ', '.join(countries)
            })
    
    # Save to CSV
    if whale_sessions:
        output_file = REPORT_DIR / "whale_analysis.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_id', 'total_debit', 'total_bets', 
                                                   'avg_session_hours', 'session_count', 'countries'])
            writer.writeheader()
            writer.writerows(whale_sessions)
    
    update_progress('whale_tracking', 'Whale tracking complete!', 100,
                    {'total_players': len(player_debit), 'whales': len(whales)})
    
    return whale_sessions


# ============================================================================
# 2. TIME-SERIES ANALYSIS BY COUNTRY
# ============================================================================

def analyze_time_series():
    """
    Map formatted_debit_at against billing_date to find peak traffic hours
    Compare patterns across different countries
    """
    update_progress('time_series', 'Starting time-series analysis...', 0)
    
    hourly_data = defaultdict(int)
    country_hourly = defaultdict(lambda: defaultdict(int))
    
    files = get_all_csv_files()
    
    for file_idx, file_path in enumerate(files, 1):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    timestamp_str = row.get('formatted_debit_at', '').strip()
                    currency = row.get('currency', '').strip()
                    
                    if not timestamp_str:
                        continue
                    
                    try:
                        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        hour = ts.hour
                        hourly_data[hour] += 1
                        
                        country = CURRENCY_COUNTRY.get(currency, 'Unknown')
                        country_hourly[country][hour] += 1
                    except ValueError:
                        pass
                    
        except Exception as e:
            print(f"    Error: {e}")
            continue
        
        pct = 10 + int((file_idx / len(files)) * 40)
        update_progress('time_series', f'Processing file {file_idx}/{len(files)}...', pct,
                        {'total_files': len(files), 'processed': file_idx})
    
    # Country summary
    country_summary = []
    for country in sorted(country_hourly.keys()):
        hours = country_hourly[country]
        total_country_bets = sum(hours.values())
        peak_hour, peak_count = max(hours.items(), key=lambda x: x[1])
        
        country_summary.append({
            'Country': country,
            'Total_Bets': total_country_bets,
            'Peak_Hour': f"{peak_hour:02d}:00",
            'Peak_Bets': peak_count,
            'Peak_Percentage': round((peak_count / total_country_bets) * 100, 2)
        })
    
    # Save results
    output_file = REPORT_DIR / "time_series_analysis.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Country', 'Total_Bets', 'Peak_Hour', 
                                               'Peak_Bets', 'Peak_Percentage'])
        writer.writeheader()
        writer.writerows(country_summary)
    
    # Hourly breakdown
    hourly_output = REPORT_DIR / "hourly_traffic.csv"
    with open(hourly_output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Hour', 'Total_Bets'])
        for hour, count in sorted(hourly_data.items()):
            writer.writerow([f"{hour:02d}:00", count])
    
    update_progress('time_series', 'Time-series analysis complete!', 100,
                    {'countries': len(country_summary), 'total_bets': sum(hourly_data.values())})
    
    return country_summary


# ============================================================================
# 3. CHASER DETECTION (PROBLEM GAMBLING INDICATOR)
# ============================================================================

def detect_chasers():
    """
    Flag players with consecutive losses followed by massive debit spikes
    Indicates chasing behavior - strong problem gambling indicator
    """
    update_progress('chaser_detection', 'Starting chaser detection...', 0)
    
    player_sequences = defaultdict(list)
    files = get_all_csv_files()
    
    for file_idx, file_path in enumerate(files, 1):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    player_id = row.get('player_id', '').strip()
                    if not player_id:
                        continue
                    
                    timestamp_str = row.get('formatted_debit_at', '').strip()
                    currency = row.get('currency', '').strip()
                    winlose = safe_float(row.get('winlose_amount', 0))
                    debit = safe_float(row.get('debit_amount', 0))
                    
                    # Convert to PHP using date-relative rate
                    winlose_php = convert_to_php(winlose, currency, timestamp_str)
                    debit_php = convert_to_php(debit, currency, timestamp_str)
                    
                    if timestamp_str:
                        try:
                            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            player_sequences[player_id].append((ts, winlose_php, debit_php))
                        except ValueError:
                            pass
                    
        except Exception as e:
            print(f"    Error: {e}")
            continue
        
        pct = 10 + int((file_idx / len(files)) * 40)
        update_progress('chaser_detection', f'Processing file {file_idx}/{len(files)}...', pct,
                        {'total_files': len(files), 'processed': file_idx})
    
    update_progress('chaser_detection', 'Analyzing player sequences...', 55,
                    {'total_players': len(player_sequences)})
    
    # Detect chasing behavior
    chasers = []
    chase_threshold_losses = 3
    chase_spike_multiplier = 3
    
    for player_id, sequence in player_sequences.items():
        if len(sequence) < 5:
            continue
        
        sequence.sort(key=lambda x: x[0])
        
        consecutive_losses = 0
        loss_start_idx = 0
        chase_events = []
        
        for idx, (ts, winlose, debit) in enumerate(sequence):
            if winlose < 0:
                if consecutive_losses == 0:
                    loss_start_idx = idx
                consecutive_losses += 1
            else:
                if consecutive_losses >= chase_threshold_losses:
                    loss_bets = sequence[loss_start_idx:idx]
                    avg_loss_debit = sum(b[2] for b in loss_bets) / len(loss_bets) if loss_bets else 0
                    
                    post_loss_bets = sequence[idx:idx+3]
                    if post_loss_bets:
                        spike_debits = [b[2] for b in post_loss_bets]
                        max_spike = max(spike_debits)
                        
                        if avg_loss_debit > 0 and max_spike > avg_loss_debit * chase_spike_multiplier:
                            chase_events.append({
                                'loss_streak': consecutive_losses,
                                'avg_loss_debit': avg_loss_debit,
                                'spike_debit': max_spike,
                                'spike_multiplier': max_spike / avg_loss_debit
                            })
                
                consecutive_losses = 0
        
        if chase_events:
            worst_chase = max(chase_events, key=lambda x: x['spike_multiplier'])
            
            chasers.append({
                'player_id': player_id,
                'total_bets': len(sequence),
                'chase_events': len(chase_events),
                'max_consecutive_losses': worst_chase['loss_streak'],
                'avg_loss_debit': round(worst_chase['avg_loss_debit'], 2),
                'spike_debit': round(worst_chase['spike_debit'], 2),
                'spike_multiplier': round(worst_chase['spike_multiplier'], 2),
                'total_debit': round(sum(b[2] for b in sequence), 2),
                'total_winlose': round(sum(b[1] for b in sequence), 2)
            })
    
    chasers.sort(key=lambda x: x['spike_multiplier'], reverse=True)
    
    # Save results
    if chasers:
        output_file = REPORT_DIR / "chaser_detection.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_id', 'total_bets', 'chase_events',
                                                   'max_consecutive_losses', 'avg_loss_debit',
                                                   'spike_debit', 'spike_multiplier',
                                                   'total_debit', 'total_winlose'])
            writer.writeheader()
            writer.writerows(chasers)
    
    update_progress('chaser_detection', 'Chaser detection complete!', 100,
                    {'total_players': len(player_sequences), 'chasers': len(chasers)})
    
    return chasers


# ============================================================================
# 4. OPERATOR PERFORMANCE ANALYSIS
# ============================================================================

def analyze_operators():
    """
    Aggregate winlose_amount by operator to see which are most profitable
    """
    update_progress('operator_analysis', 'Starting operator analysis...', 0)
    
    operator_data = defaultdict(lambda: {
        'total_winlose': 0.0,
        'total_debit': 0.0,
        'total_bets': 0,
        'players': set(),
        'countries': set()
    })
    
    files = get_all_csv_files()
    
    for file_idx, file_path in enumerate(files, 1):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    operator = row.get('operator_name', '').strip()
                    if not operator:
                        operator = 'UNKNOWN'
                    
                    winlose = safe_float(row.get('winlose_amount', 0))
                    debit = safe_float(row.get('debit_amount', 0))
                    player_id = row.get('player_id', '').strip()
                    currency = row.get('currency', '').strip()
                    timestamp_str = row.get('formatted_debit_at', '').strip()
                    
                    # Convert to PHP using date-relative rate
                    winlose_php = convert_to_php(winlose, currency, timestamp_str)
                    debit_php = convert_to_php(debit, currency, timestamp_str)
                    
                    country = get_country(currency)
                    
                    operator_data[operator]['total_winlose'] += winlose_php
                    operator_data[operator]['total_debit'] += debit_php
                    operator_data[operator]['total_bets'] += 1
                    if player_id:
                        operator_data[operator]['players'].add(player_id)
                    operator_data[operator]['countries'].add(country)
                    
        except Exception as e:
            print(f"    Error: {e}")
            continue
        
        pct = 10 + int((file_idx / len(files)) * 40)
        update_progress('operator_analysis', f'Processing file {file_idx}/{len(files)}...', pct,
                        {'total_files': len(files), 'processed': file_idx})
    
    # Calculate metrics
    operator_summary = []
    for operator, data in operator_data.items():
        total_winlose = data['total_winlose']
        total_debit = data['total_debit']
        total_bets = data['total_bets']
        
        roi = ((total_debit + total_winlose) / total_debit * 100) if total_debit > 0 else 0
        avg_bet = total_debit / total_bets if total_bets > 0 else 0
        
        operator_summary.append({
            'Operator': operator,
            'Total_Bets': total_bets,
            'Total_Debit': round(total_debit, 2),
            'Total_Winlose': round(total_winlose, 2),
            'Operator_ROI_%': round(roi, 2),
            'Avg_Bet': round(avg_bet, 2),
            'Unique_Players': len(data['players']),
            'Countries': ', '.join(sorted(data['countries']))
        })
    
    operator_summary.sort(key=lambda x: x['Total_Debit'], reverse=True)
    
    # Save results
    output_file = REPORT_DIR / "operator_performance.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Operator', 'Total_Bets', 'Total_Debit',
                                               'Total_Winlose', 'Operator_ROI_%',
                                               'Avg_Bet', 'Unique_Players', 'Countries'])
        writer.writeheader()
        writer.writerows(operator_summary)
    
    update_progress('operator_analysis', 'Operator analysis complete!', 100,
                    {'total_operators': len(operator_summary)})
    
    return operator_summary


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("="*80)
    print("CASINO DATA ANALYSIS TOOL")
    print("="*80)
    print(f"Target Folder: {FOLDER}")
    print(f"Report Directory: {REPORT_DIR}")
    
    update_progress('initializing', 'Starting analysis...', 0)
    
    if not FOLDER.exists():
        print(f"ERROR: Folder not found: {FOLDER}")
        update_progress('error', 'Folder not found', 0)
        return
    
    csv_files = get_all_csv_files()
    print(f"\nFound {len(csv_files)} CSV files")
    update_progress('initializing', f'Found {len(csv_files)} CSV files', 5,
                    {'total_files': len(csv_files)})
    
    if len(csv_files) == 0:
        print("ERROR: No CSV files found!")
        update_progress('error', 'No CSV files found', 0)
        return
    
    try:
        # 1. Whale Tracking
        whale_results = analyze_whales()
        
        # 2. Time-Series Analysis
        time_results = analyze_time_series()
        
        # 3. Chaser Detection
        chaser_results = detect_chasers()
        
        # 4. Operator Performance
        operator_results = analyze_operators()
        
        update_progress('complete', 'All analyses complete!', 100, {
            'whales': len(whale_results) if whale_results else 0,
            'countries': len(time_results) if time_results else 0,
            'chasers': len(chaser_results) if chaser_results else 0,
            'operators': len(operator_results) if operator_results else 0
        })
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE - SUMMARY")
        print("="*80)
        print(f"[OK] Whale analysis: {REPORT_DIR / 'whale_analysis.csv'}")
        print(f"[OK] Time-series analysis: {REPORT_DIR / 'time_series_analysis.csv'}")
        print(f"[OK] Chaser detection: {REPORT_DIR / 'chaser_detection.csv'}")
        print(f"[OK] Operator performance: {REPORT_DIR / 'operator_performance.csv'}")
        print("\nAll reports generated successfully!")
        
    except Exception as e:
        print(f"\nERROR during analysis: {e}")
        import traceback
        traceback.print_exc()
        update_progress('error', str(e), 0)


if __name__ == "__main__":
    main()
