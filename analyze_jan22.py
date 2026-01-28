#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze why no trades happened on January 22, 2026"""

import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

MSK = timezone(timedelta(hours=3))
target_date = '2026-01-22'

cycles = []
skips = []
trades = []
decisions = []

print(f"Loading audit log...")

with open('audit_logs/trades_audit.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except:
            continue
        
        ts = e.get('ts_utc')
        if not ts:
            continue
        
        try:
            dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            dt_msk = dt_utc.astimezone(MSK)
        except:
            continue
        
        if dt_msk.strftime('%Y-%m-%d') != target_date:
            continue
        
        event = e.get('event')
        if event == 'cycle':
            cycles.append((dt_msk, e))
        elif event == 'skip':
            skips.append((dt_msk, e))
        elif event == 'trade':
            trades.append((dt_msk, e))
        elif event == 'decision':
            decisions.append((dt_msk, e))

print("=" * 60)
print(f"ANALYSIS FOR {target_date} (MSK)")
print("=" * 60)
print(f"Cycles (heartbeats): {len(cycles)}")
print(f"Skip events: {len(skips)}")
print(f"Trade events: {len(trades)}")
print(f"Decision events: {len(decisions)}")
print()

if cycles:
    print("--- First and Last Cycle ---")
    first = cycles[0]
    last = cycles[-1]
    print(f"First: {first[0].strftime('%H:%M:%S')} | equity={first[1].get('equity')}, cash={first[1].get('cash')}, allow_entries={first[1].get('allow_entries')}, open_positions={first[1].get('open_positions')}")
    print(f"Last:  {last[0].strftime('%H:%M:%S')} | equity={last[1].get('equity')}, cash={last[1].get('cash')}, allow_entries={last[1].get('allow_entries')}, open_positions={last[1].get('open_positions')}")
    print()
    
    # Check allow_entries
    blocked_cycles = [c for c in cycles if c[1].get('allow_entries') == False]
    allowed_cycles = [c for c in cycles if c[1].get('allow_entries') == True]
    print(f"Cycles with allow_entries=True: {len(allowed_cycles)}")
    print(f"Cycles with allow_entries=False: {len(blocked_cycles)}")
    
    if blocked_cycles:
        print(f"\n!!! BLOCKING DETECTED !!!")
        print(f"First block at: {blocked_cycles[0][0].strftime('%H:%M:%S')}")
        first_block = blocked_cycles[0][1]
        print(f"  equity={first_block.get('equity')}, cash={first_block.get('cash')}")
    print()

if skips:
    print("--- All SKIP Events (reasons for skipping) ---")
    reasons = defaultdict(list)
    for dt, e in skips:
        reason = e.get('skip_reason', 'unknown')
        reasons[reason].append((dt, e))
    
    print("\nSummary of skip reasons:")
    for reason, events in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {reason}: {len(events)} times")
        # Show first occurrence with details
        first_ev = events[0]
        print(f"    First at {first_ev[0].strftime('%H:%M:%S')}")
        if 'details' in first_ev[1]:
            print(f"    Details: {first_ev[1]['details']}")
        if 'equity' in first_ev[1]:
            print(f"    Equity: {first_ev[1].get('equity')}, Cash: {first_ev[1].get('cash')}")
else:
    print("--- NO SKIP EVENTS ---")
print()

if decisions:
    print("--- Decision Events (buy/sell signals) ---")
    buy_signals = [d for d in decisions if d[1].get('signal') == 'buy']
    sell_signals = [d for d in decisions if d[1].get('signal') == 'sell']
    hold_signals = [d for d in decisions if d[1].get('signal') == 'hold']
    
    print(f"Buy signals: {len(buy_signals)}")
    print(f"Sell signals: {len(sell_signals)}")
    print(f"Hold signals: {len(hold_signals)}")
    
    if buy_signals:
        print("\nBuy signals details:")
        for dt, e in buy_signals[:10]:  # First 10
            print(f"  {dt.strftime('%H:%M:%S')} | {e.get('symbol')} | confidence={e.get('confidence')}, executed={e.get('executed')}")
            if e.get('skip_reason'):
                print(f"    Skip reason: {e.get('skip_reason')}")
else:
    print("--- NO DECISION EVENTS ---")
print()

if trades:
    print("--- Trade Events ---")
    for dt, e in trades:
        print(f"  {dt.strftime('%H:%M:%S')} | {e.get('action')} {e.get('symbol')} qty={e.get('qty_lots')} @ {e.get('price')}")
else:
    print("--- NO TRADES ON THIS DAY ---")
print()

# Final diagnosis
print("=" * 60)
print("DIAGNOSIS")
print("=" * 60)

if not cycles:
    print("BOT WAS NOT RUNNING on this day (no cycle events)")
elif len(cycles) < 10:
    print(f"BOT RAN VERY BRIEFLY - only {len(cycles)} cycles")
    print("Check if bot was started/stopped multiple times or crashed")
else:
    if blocked_cycles and len(blocked_cycles) > len(cycles) * 0.5:
        print("MAIN ISSUE: allow_entries=False for most of the day")
        print("This means daily loss limit was triggered")
        if skips:
            for reason, events in reasons.items():
                if 'loss_limit' in reason.lower() or 'drawdown' in reason.lower():
                    print(f"  Confirmed: {reason}")
    elif not decisions:
        print("NO DECISION EVENTS - bot may not have analyzed any symbols")
        print("Check if SYMBOLS list is configured and market data is available")
    elif decisions and not buy_signals:
        print("NO BUY SIGNALS - strategy did not find any buy opportunities")
        print("This could be normal if market conditions were unfavorable")
    elif buy_signals and not trades:
        print("BUY SIGNALS EXISTED but no trades executed")
        print("Check skip reasons above for why signals were not executed")
    else:
        print("Unable to determine specific cause - review logs above")

# -*- coding: utf-8 -*-
"""Analyze why no trades happened on January 22, 2026"""

import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

MSK = timezone(timedelta(hours=3))
target_date = '2026-01-22'

cycles = []
skips = []
trades = []
decisions = []

print(f"Loading audit log...")

with open('audit_logs/trades_audit.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except:
            continue
        
        ts = e.get('ts_utc')
        if not ts:
            continue
        
        try:
            dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            dt_msk = dt_utc.astimezone(MSK)
        except:
            continue
        
        if dt_msk.strftime('%Y-%m-%d') != target_date:
            continue
        
        event = e.get('event')
        if event == 'cycle':
            cycles.append((dt_msk, e))
        elif event == 'skip':
            skips.append((dt_msk, e))
        elif event == 'trade':
            trades.append((dt_msk, e))
        elif event == 'decision':
            decisions.append((dt_msk, e))

print("=" * 60)
print(f"ANALYSIS FOR {target_date} (MSK)")
print("=" * 60)
print(f"Cycles (heartbeats): {len(cycles)}")
print(f"Skip events: {len(skips)}")
print(f"Trade events: {len(trades)}")
print(f"Decision events: {len(decisions)}")
print()

if cycles:
    print("--- First and Last Cycle ---")
    first = cycles[0]
    last = cycles[-1]
    print(f"First: {first[0].strftime('%H:%M:%S')} | equity={first[1].get('equity')}, cash={first[1].get('cash')}, allow_entries={first[1].get('allow_entries')}, open_positions={first[1].get('open_positions')}")
    print(f"Last:  {last[0].strftime('%H:%M:%S')} | equity={last[1].get('equity')}, cash={last[1].get('cash')}, allow_entries={last[1].get('allow_entries')}, open_positions={last[1].get('open_positions')}")
    print()
    
    # Check allow_entries
    blocked_cycles = [c for c in cycles if c[1].get('allow_entries') == False]
    allowed_cycles = [c for c in cycles if c[1].get('allow_entries') == True]
    print(f"Cycles with allow_entries=True: {len(allowed_cycles)}")
    print(f"Cycles with allow_entries=False: {len(blocked_cycles)}")
    
    if blocked_cycles:
        print(f"\n!!! BLOCKING DETECTED !!!")
        print(f"First block at: {blocked_cycles[0][0].strftime('%H:%M:%S')}")
        first_block = blocked_cycles[0][1]
        print(f"  equity={first_block.get('equity')}, cash={first_block.get('cash')}")
    print()

if skips:
    print("--- All SKIP Events (reasons for skipping) ---")
    reasons = defaultdict(list)
    for dt, e in skips:
        reason = e.get('skip_reason', 'unknown')
        reasons[reason].append((dt, e))
    
    print("\nSummary of skip reasons:")
    for reason, events in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {reason}: {len(events)} times")
        # Show first occurrence with details
        first_ev = events[0]
        print(f"    First at {first_ev[0].strftime('%H:%M:%S')}")
        if 'details' in first_ev[1]:
            print(f"    Details: {first_ev[1]['details']}")
        if 'equity' in first_ev[1]:
            print(f"    Equity: {first_ev[1].get('equity')}, Cash: {first_ev[1].get('cash')}")
else:
    print("--- NO SKIP EVENTS ---")
print()

if decisions:
    print("--- Decision Events (buy/sell signals) ---")
    buy_signals = [d for d in decisions if d[1].get('signal') == 'buy']
    sell_signals = [d for d in decisions if d[1].get('signal') == 'sell']
    hold_signals = [d for d in decisions if d[1].get('signal') == 'hold']
    
    print(f"Buy signals: {len(buy_signals)}")
    print(f"Sell signals: {len(sell_signals)}")
    print(f"Hold signals: {len(hold_signals)}")
    
    if buy_signals:
        print("\nBuy signals details:")
        for dt, e in buy_signals[:10]:  # First 10
            print(f"  {dt.strftime('%H:%M:%S')} | {e.get('symbol')} | confidence={e.get('confidence')}, executed={e.get('executed')}")
            if e.get('skip_reason'):
                print(f"    Skip reason: {e.get('skip_reason')}")
else:
    print("--- NO DECISION EVENTS ---")
print()

if trades:
    print("--- Trade Events ---")
    for dt, e in trades:
        print(f"  {dt.strftime('%H:%M:%S')} | {e.get('action')} {e.get('symbol')} qty={e.get('qty_lots')} @ {e.get('price')}")
else:
    print("--- NO TRADES ON THIS DAY ---")
print()

# Final diagnosis
print("=" * 60)
print("DIAGNOSIS")
print("=" * 60)

if not cycles:
    print("BOT WAS NOT RUNNING on this day (no cycle events)")
elif len(cycles) < 10:
    print(f"BOT RAN VERY BRIEFLY - only {len(cycles)} cycles")
    print("Check if bot was started/stopped multiple times or crashed")
else:
    if blocked_cycles and len(blocked_cycles) > len(cycles) * 0.5:
        print("MAIN ISSUE: allow_entries=False for most of the day")
        print("This means daily loss limit was triggered")
        if skips:
            for reason, events in reasons.items():
                if 'loss_limit' in reason.lower() or 'drawdown' in reason.lower():
                    print(f"  Confirmed: {reason}")
    elif not decisions:
        print("NO DECISION EVENTS - bot may not have analyzed any symbols")
        print("Check if SYMBOLS list is configured and market data is available")
    elif decisions and not buy_signals:
        print("NO BUY SIGNALS - strategy did not find any buy opportunities")
        print("This could be normal if market conditions were unfavorable")
    elif buy_signals and not trades:
        print("BUY SIGNALS EXISTED but no trades executed")
        print("Check skip reasons above for why signals were not executed")
    else:
        print("Unable to determine specific cause - review logs above")

# -*- coding: utf-8 -*-
"""Analyze why no trades happened on January 22, 2026"""

import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

MSK = timezone(timedelta(hours=3))
target_date = '2026-01-22'

cycles = []
skips = []
trades = []
decisions = []

print(f"Loading audit log...")

with open('audit_logs/trades_audit.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except:
            continue
        
        ts = e.get('ts_utc')
        if not ts:
            continue
        
        try:
            dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            dt_msk = dt_utc.astimezone(MSK)
        except:
            continue
        
        if dt_msk.strftime('%Y-%m-%d') != target_date:
            continue
        
        event = e.get('event')
        if event == 'cycle':
            cycles.append((dt_msk, e))
        elif event == 'skip':
            skips.append((dt_msk, e))
        elif event == 'trade':
            trades.append((dt_msk, e))
        elif event == 'decision':
            decisions.append((dt_msk, e))

print("=" * 60)
print(f"ANALYSIS FOR {target_date} (MSK)")
print("=" * 60)
print(f"Cycles (heartbeats): {len(cycles)}")
print(f"Skip events: {len(skips)}")
print(f"Trade events: {len(trades)}")
print(f"Decision events: {len(decisions)}")
print()

if cycles:
    print("--- First and Last Cycle ---")
    first = cycles[0]
    last = cycles[-1]
    print(f"First: {first[0].strftime('%H:%M:%S')} | equity={first[1].get('equity')}, cash={first[1].get('cash')}, allow_entries={first[1].get('allow_entries')}, open_positions={first[1].get('open_positions')}")
    print(f"Last:  {last[0].strftime('%H:%M:%S')} | equity={last[1].get('equity')}, cash={last[1].get('cash')}, allow_entries={last[1].get('allow_entries')}, open_positions={last[1].get('open_positions')}")
    print()
    
    # Check allow_entries
    blocked_cycles = [c for c in cycles if c[1].get('allow_entries') == False]
    allowed_cycles = [c for c in cycles if c[1].get('allow_entries') == True]
    print(f"Cycles with allow_entries=True: {len(allowed_cycles)}")
    print(f"Cycles with allow_entries=False: {len(blocked_cycles)}")
    
    if blocked_cycles:
        print(f"\n!!! BLOCKING DETECTED !!!")
        print(f"First block at: {blocked_cycles[0][0].strftime('%H:%M:%S')}")
        first_block = blocked_cycles[0][1]
        print(f"  equity={first_block.get('equity')}, cash={first_block.get('cash')}")
    print()

if skips:
    print("--- All SKIP Events (reasons for skipping) ---")
    reasons = defaultdict(list)
    for dt, e in skips:
        reason = e.get('skip_reason', 'unknown')
        reasons[reason].append((dt, e))
    
    print("\nSummary of skip reasons:")
    for reason, events in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {reason}: {len(events)} times")
        # Show first occurrence with details
        first_ev = events[0]
        print(f"    First at {first_ev[0].strftime('%H:%M:%S')}")
        if 'details' in first_ev[1]:
            print(f"    Details: {first_ev[1]['details']}")
        if 'equity' in first_ev[1]:
            print(f"    Equity: {first_ev[1].get('equity')}, Cash: {first_ev[1].get('cash')}")
else:
    print("--- NO SKIP EVENTS ---")
print()

if decisions:
    print("--- Decision Events (buy/sell signals) ---")
    buy_signals = [d for d in decisions if d[1].get('signal') == 'buy']
    sell_signals = [d for d in decisions if d[1].get('signal') == 'sell']
    hold_signals = [d for d in decisions if d[1].get('signal') == 'hold']
    
    print(f"Buy signals: {len(buy_signals)}")
    print(f"Sell signals: {len(sell_signals)}")
    print(f"Hold signals: {len(hold_signals)}")
    
    if buy_signals:
        print("\nBuy signals details:")
        for dt, e in buy_signals[:10]:  # First 10
            print(f"  {dt.strftime('%H:%M:%S')} | {e.get('symbol')} | confidence={e.get('confidence')}, executed={e.get('executed')}")
            if e.get('skip_reason'):
                print(f"    Skip reason: {e.get('skip_reason')}")
else:
    print("--- NO DECISION EVENTS ---")
print()

if trades:
    print("--- Trade Events ---")
    for dt, e in trades:
        print(f"  {dt.strftime('%H:%M:%S')} | {e.get('action')} {e.get('symbol')} qty={e.get('qty_lots')} @ {e.get('price')}")
else:
    print("--- NO TRADES ON THIS DAY ---")
print()

# Final diagnosis
print("=" * 60)
print("DIAGNOSIS")
print("=" * 60)

if not cycles:
    print("BOT WAS NOT RUNNING on this day (no cycle events)")
elif len(cycles) < 10:
    print(f"BOT RAN VERY BRIEFLY - only {len(cycles)} cycles")
    print("Check if bot was started/stopped multiple times or crashed")
else:
    if blocked_cycles and len(blocked_cycles) > len(cycles) * 0.5:
        print("MAIN ISSUE: allow_entries=False for most of the day")
        print("This means daily loss limit was triggered")
        if skips:
            for reason, events in reasons.items():
                if 'loss_limit' in reason.lower() or 'drawdown' in reason.lower():
                    print(f"  Confirmed: {reason}")
    elif not decisions:
        print("NO DECISION EVENTS - bot may not have analyzed any symbols")
        print("Check if SYMBOLS list is configured and market data is available")
    elif decisions and not buy_signals:
        print("NO BUY SIGNALS - strategy did not find any buy opportunities")
        print("This could be normal if market conditions were unfavorable")
    elif buy_signals and not trades:
        print("BUY SIGNALS EXISTED but no trades executed")
        print("Check skip reasons above for why signals were not executed")
    else:
        print("Unable to determine specific cause - review logs above")




