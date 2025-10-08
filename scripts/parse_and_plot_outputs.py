#!/usr/bin/env python3
"""
parse_and_plot_outputs.py

Usage:
    python3 scripts/parse_and_plot_outputs.py --output-dir ./output --baseline-key baseline --save-csv results.csv

The script walks the output directory, parses ChampSim run output files and extracts:
 - final cumulative IPC
 - L2 MPKI (or compute from L2 misses + instructions if necessary)
 - prefetch stats (if printed)

It creates:
 - results.csv (table of measurements)
 - speedup_plot.png (speedup vs table size for each trace)
 - mpki_plot.png (L2 MPKI comparison)
"""

import re
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

# -------------------------
# Helper parsers
# -------------------------
re_finished = re.compile(r'Finished\s+CPU\s+\d+\s+instructions:\s*([0-9]+)\s+cycles:\s*([0-9]+)\s+cumulative\s+IPC:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_heartbeat = re.compile(r'cumulative\s+IPC:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_l2_mpki = re.compile(r'l2\s*mpki[:\s]+([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_l2_misses = re.compile(r'l2\s+total\s+miss(?:es)?:\s*([0-9]+)', re.IGNORECASE)
re_instructions = re.compile(r'CPU\s+\d+\s+instructions:\s*([0-9]+)', re.IGNORECASE)
re_pref_issued = re.compile(r'Prefetches issued[:\s]+([0-9]+)', re.IGNORECASE)
re_pref_useful = re.compile(r'Prefetches useful[:\s]+(?:\(approx\):\s*)?([0-9]+)', re.IGNORECASE)

# Try to infer variant from filename
def infer_variant_from_name(name):
    lname = name.lower()
    if 'baseline' in lname or 'no' == lname or 'champsim-no' in lname:
        return 'baseline'
    if '32' in lname and not '128' in lname:
        return 'table32'
    if '64' in lname and not '128' in lname:
        return 'table64'
    if '128' in lname:
        return 'table128'
    # fallback
    if 'pref' in lname or 'offset' in lname:
        # try to parse digits
        m = re.search(r'(\d+)', lname)
        if m:
            n = int(m.group(1))
            return f'table{n}'
        return 'prefetcher'
    return 'unknown'

def parse_file(path):
    data = {
        'file': os.path.basename(path),
        'ipc': None,
        'l2_mpki': None,
        'l2_misses': None,
        'instructions': None,
        'prefetch_issued': None,
        'prefetch_useful': None,
    }
    with open(path, 'r', errors='ignore') as f:
        text = f.read()

    # try finished line first
    m = re_finished.search(text)
    if m:
        instr = int(m.group(1))
        cycles = int(m.group(2))
        ipc = float(m.group(3))
        data['ipc'] = ipc
        data['instructions'] = instr

    # If not found, try last heartbeat cumulative IPC
    if data['ipc'] is None:
        hearts = re_heartbeat.findall(text)
        if hearts:
            data['ipc'] = float(hearts[-1])

    # l2 mpki
    m = re_l2_mpki.search(text)
    if m:
        data['l2_mpki'] = float(m.group(1))

    # l2 misses
    m = re_l2_misses.search(text)
    if m:
        data['l2_misses'] = int(m.group(1))

    # try to find instructions if not found
    if data['instructions'] is None:
        m = re_instructions.search(text)
        if m:
            data['instructions'] = int(m.group(1))

    # compute mpki fallback
    if data['l2_mpki'] is None and data['l2_misses'] is not None and data['instructions'] is not None and data['instructions'] > 0:
        data['l2_mpki'] = (data['l2_misses'] / data['instructions']) * 1000.0

    # prefetch stats (optional)
    m = re_pref_issued.search(text)
    if m:
        data['prefetch_issued'] = int(m.group(1))
    m = re_pref_useful.search(text)
    if m:
        data['prefetch_useful'] = int(m.group(1))

    return data

# -------------------------
# Main
# -------------------------
def main(output_dir, save_csv):
    rows = []
    # iterate trace subfolders
    for trace_folder in sorted(os.listdir(output_dir)):
        folder_path = os.path.join(output_dir, trace_folder)
        if not os.path.isdir(folder_path):
            continue
        # collect files in the folder
        for fname in sorted(os.listdir(folder_path)):
            if not (fname.lower().endswith('.txt') or fname.lower().endswith('.out') or fname.lower().endswith('.log')):
                continue
            fpath = os.path.join(folder_path, fname)
            parsed = parse_file(fpath)
            variant = infer_variant_from_name(fname)
            parsed['trace_folder'] = trace_folder
            parsed['variant'] = variant
            rows.append(parsed)

    df = pd.DataFrame(rows)
    # Normalize variant names if needed
    # Pivot table: rows per trace_folder and variant
    df.to_csv(save_csv, index=False)
    print(f"Saved parsed table to {save_csv}")
    print(df)

    # For plotting, create speedup plots per trace (baseline required per trace)
    traces = df['trace_folder'].unique()
    for t in traces:
        sub = df[df['trace_folder'] == t]
        # find baseline IPC for this trace
        base = None
        base_row = sub[sub['variant'] == 'baseline']
        if not base_row.empty:
            base = float(base_row['ipc'].iloc[0])
        else:
            # try unknown labeled baseline
            if len(sub) > 0:
                # pick the row with variant 'unknown' or the first row as baseline -- ask user to confirm
                base = float(sub['ipc'].iloc[0])
                print(f"[WARN] No explicit baseline found for trace {t}. Using {sub['file'].iloc[0]} as baseline.")
            else:
                continue

        # select prefetch variants in order 32,64,128
        variants = ['table32', 'table64', 'table128']
        xs = []
        ys = []
        mpki_vals = []
        labels = []
        for v in variants:
            r = sub[sub['variant'] == v]
            if r.empty:
                # skip, but keep placeholder
                continue
            ipc_v = float(r['ipc'].iloc[0])
            mpki_v = r['l2_mpki'].iloc[0] if pd.notnull(r['l2_mpki'].iloc[0]) else None
            speedup = ipc_v / base if base and base != 0 else None
            xs.append(int(v.replace('table','')))
            ys.append(speedup)
            mpki_vals.append(mpki_v)
            labels.append(v)

        # plot speedup curve (if any)
        if xs:
            plt.figure(figsize=(6,4))
            plt.plot(xs, ys, marker='o')
            plt.title(f"Speedup vs Prefetcher Table Size — {t}")
            plt.xlabel("Prefetcher Table size (entries)")
            plt.ylabel("Speedup (IPC_prefetch / IPC_baseline)")
            plt.grid(True)
            plt.axhline(1.0, color='gray', linestyle='--')
            out_png = os.path.join(output_dir, f"speedup_{t}.png")
            plt.savefig(out_png)
            plt.close()
            print(f"Saved {out_png}")

        # plot mpki bar (if available)
        if xs and any(x is not None for x in mpki_vals):
            plt.figure(figsize=(6,4))
            plt.bar(xs, mpki_vals)
            plt.title(f"L2 MPKI vs Table Size — {t}")
            plt.xlabel("Table size (entries)")
            plt.ylabel("L2 MPKI")
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            out_png = os.path.join(output_dir, f"mpki_{t}.png")
            plt.savefig(out_png)
            plt.close()
            print(f"Saved {out_png}")

    print("Done.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='./output', help='Path to output folder')
    parser.add_argument('--save-csv', default='results.csv', help='CSV path to save parsed results')
    args = parser.parse_args()
    main(args.output_dir, args.save_csv)
