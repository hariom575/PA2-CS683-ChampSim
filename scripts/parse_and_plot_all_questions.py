#!/usr/bin/env python3
"""
parse_and_plot_all_questions.py

Parses ChampSim output directories (output/) and extracts IPC, L1D/L2/LLC MPKI, prefetch stats.
Generates CSV and PNG plots for:
 - Q1: Prefetcher table-size study (table32/table64/table128 vs baseline)
 - Q2: Exclusive vs Non-Inclusive comparison (IPC and MPKIs)
 - Q3: Exclusive-prefetcher study: two speedup plots using two baselines:
       (a) non-inclusive baseline (no prefetch)
       (b) exclusive baseline (no prefetch)

Usage:
    python3 scripts/parse_and_plot_all_questions.py --output-dir ./output --save-csv outputs_parsed_all.csv
"""
import os, re, argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

# --- regexes for extracting values ---
re_finished = re.compile(r'CPU\s+\d+\s+cumulative\s+IPC:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_l1d_mpki = re.compile(r'L1D TOTAL.*MPKI:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_l2c_mpki = re.compile(r'L2C TOTAL.*MPKI:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_llc_mpki = re.compile(r'LLC TOTAL.*MPKI:\s*([0-9]*\.?[0-9]+)', re.IGNORECASE)
re_pref_issued = re.compile(r'Prefetches issued[:\s]+([0-9]+)', re.IGNORECASE)
re_pref_useful = re.compile(r'Prefetches useful[:\s]+(?:\(approx\):\s*)?([0-9]+)', re.IGNORECASE)

# flexible variant inference from filename
def infer_variant(fname):
    s = fname.lower()
    # baseline non-inclusive
    if 'baseline' in s and 'exclusive' not in s:
        return 'baseline_noninc'
    if 'baseline' in s and 'exclusive' in s:
        return 'baseline_exclusive'  # rarely used
    # exclusive baseline (named maybe 'exclusive_cache.txt' or 'exclusive_baseline')
    if ('exclusive' in s) and ('pref' not in s and 'offset' not in s and 'table' not in s):
        return 'baseline_exclusive'
    # exclusive prefetcher outputs (exclusive prefetcher runs)
    if 'exclusive' in s and ('32' in s or '64' in s or '128' in s or 'pref' in s or 'offset' in s):
        # try to detect table size
        if '128' in s: return 'exclusive_table128'
        if '64' in s: return 'exclusive_table64'
        if '32' in s: return 'exclusive_table32'
        # fallback
        return 'exclusive_prefetcher'
    # non-inclusive prefetcher runs (table sizes)
    if ('table128' in s) or ('128' in s and 'exclusive' not in s):
        return 'table128'
    if ('table64' in s) or ('64' in s and 'exclusive' not in s):
        return 'table64'
    if ('table32' in s) or ('32' in s and 'exclusive' not in s):
        return 'table32'
    # other heuristics
    if 'pref' in s or 'offset' in s:
        # find digits
        m = re.search(r'(\d+)', s)
        if m:
            n = int(m.group(1))
            return f'table{n}'
        return 'prefetcher_unknown'
    # fallback unknown
    return 'unknown'

def parse_file(path):
    with open(path, 'r', errors='ignore') as f:
        text = f.read()
    res = {
        'file': os.path.basename(path),
        'ipc': None,
        'l1d_mpki': None,
        'l2_mpki': None,
        'llc_mpki': None,
        'prefetch_issued': None,
        'prefetch_useful': None,
    }
    m = re_finished.search(text)
    if m:
        try:
            res['ipc'] = float(m.group(1))
        except:
            res['ipc'] = None
    # MPKIs
    m = re_l1d_mpki.search(text)
    if m: res['l1d_mpki'] = float(m.group(1))
    m = re_l2c_mpki.search(text)
    if m: res['l2_mpki'] = float(m.group(1))
    m = re_llc_mpki.search(text)
    if m: res['llc_mpki'] = float(m.group(1))
    # prefetch stats if present
    m = re_pref_issued.search(text)
    if m: res['prefetch_issued'] = int(m.group(1))
    m = re_pref_useful.search(text)
    if m: res['prefetch_useful'] = int(m.group(1))
    return res

def main(output_dir, save_csv):
    rows = []
    # walk trace subfolders
    for trace_folder in sorted(os.listdir(output_dir)):
        folder = os.path.join(output_dir, trace_folder)
        if not os.path.isdir(folder): continue
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith(('.txt', '.out', '.log')): continue
            path = os.path.join(folder, fname)
            parsed = parse_file(path)
            variant = infer_variant(fname)
            parsed['trace_folder'] = trace_folder
            parsed['variant'] = variant
            rows.append(parsed)

    df = pd.DataFrame(rows)
    df.to_csv(save_csv, index=False)
    print(f"Saved parsed data to {save_csv}")
    print(df)

    # For each trace, make Q1/Q2/Q3 plots as available
    traces = sorted(df['trace_folder'].unique())
    for t in traces:
        sub = df[df['trace_folder'] == t]
        print(f"\n=== Trace: {t} ===")
        # find non-inclusive baseline
        base_non = sub[sub['variant'] == 'baseline_noninc']
        base_excl = sub[sub['variant'] == 'baseline_exclusive']

        if not base_non.empty:
            base_non_ipc = float(base_non['ipc'].iloc[0])
            print(f"Non-inclusive baseline IPC: {base_non_ipc:.6f}")
        else:
            base_non_ipc = None
            print("No non-inclusive baseline found for this trace.")

        if not base_excl.empty:
            base_excl_ipc = float(base_excl['ipc'].iloc[0])
            print(f"Exclusive baseline IPC: {base_excl_ipc:.6f}")
        else:
            base_excl_ipc = None
            print("No exclusive baseline found for this trace.")

        # Q1: prefetcher table sizes (non-exclusive)
        variants_q1 = ['table32','table64','table128']
        xs, ys, mpki_vals = [], [], []
        for v in variants_q1:
            row = sub[sub['variant'] == v]
            if row.empty: continue
            ipc_v = float(row['ipc'].iloc[0])
            xs.append(int(v.replace('table','')))
            # speedup wrt non-inclusive baseline if exists; else skip
            if base_non_ipc:
                ys.append(ipc_v / base_non_ipc)
            else:
                ys.append(None)
            mpki_vals.append(row['l2_mpki'].iloc[0] if pd.notnull(row['l2_mpki'].iloc[0]) else None)

        # plot Q1 speedup vs table size (single baseline: non-inclusive)
        if xs and any(y is not None for y in ys):
            plt.figure(figsize=(6,4))
            plt.plot(xs, ys, marker='o')
            plt.title(f"Q1: Prefetcher Speedup vs Table Size — {t}")
            plt.xlabel("Table size (entries)")
            plt.ylabel("Speedup (IPC_prefetch / IPC_noninc_baseline)")
            plt.grid(True)
            plt.axhline(1.0, color='gray', linestyle='--')
            out = os.path.join(output_dir, f"q1_speedup_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

        # Q1: L2 MPKI vs table size
        if xs and any(m is not None for m in mpki_vals):
            plt.figure(figsize=(6,4))
            plt.bar(xs, mpki_vals)
            plt.title(f"Q1: L2 MPKI vs Table Size — {t}")
            plt.xlabel("Table size (entries)")
            plt.ylabel("L2 MPKI")
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            out = os.path.join(output_dir, f"q1_mpki_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

        # Q2: Exclusive vs Non-Inclusive comparison (IPC + MPKIs)
        if (not base_non.empty) and (not base_excl.empty):
            excl_row = base_excl.iloc[0]
            ipc_non = base_non_ipc
            ipc_excl = float(excl_row['ipc'])
            speedup = ipc_excl / ipc_non if ipc_non else None
            l1d_non = float(base_non['l1d_mpki'].iloc[0]) if pd.notnull(base_non['l1d_mpki'].iloc[0]) else None
            l2_non  = float(base_non['l2_mpki'].iloc[0]) if pd.notnull(base_non['l2_mpki'].iloc[0]) else None
            llc_non = float(base_non['llc_mpki'].iloc[0]) if pd.notnull(base_non['llc_mpki'].iloc[0]) else None
            l1d_ex = float(excl_row['l1d_mpki']) if pd.notnull(excl_row['l1d_mpki']) else None
            l2_ex  = float(excl_row['l2_mpki']) if pd.notnull(excl_row['l2_mpki']) else None
            llc_ex = float(excl_row['llc_mpki']) if pd.notnull(excl_row['llc_mpki']) else None

            print("Q2: Exclusive vs Non-Inclusive")
            print(f"  Non-inc IPC: {ipc_non:.6f}, Exclusive IPC: {ipc_excl:.6f}, Speedup: {speedup:.4f}")
            print(f"  L1D MPKI: non-inc {l1d_non}, exclusive {l1d_ex}")
            print(f"  L2 MPKI: non-inc {l2_non}, exclusive {l2_ex}")
            print(f"  LLC MPKI: non-inc {llc_non}, exclusive {llc_ex}")

            # IPC bar chart
            plt.figure(figsize=(5,4))
            plt.bar(['non-inclusive','exclusive'], [ipc_non, ipc_excl], color=['gray','tab:blue'])
            plt.title(f"Q2: Exclusive vs Non-Inclusive IPC — {t}")
            plt.ylabel("IPC")
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            out = os.path.join(output_dir, f"q2_ipc_cmp_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

            # MPKI grouped bar chart for L1D, L2, LLC
            labels = []
            non_vals = []
            ex_vals = []
            for label, nval, evalv in [('L1D', l1d_non, l1d_ex), ('L2', l2_non, l2_ex), ('LLC', llc_non, llc_ex)]:
                labels.append(label)
                non_vals.append(nval if nval is not None else 0.0)
                ex_vals.append(evalv if evalv is not None else 0.0)
            x = range(len(labels))
            width = 0.35
            plt.figure(figsize=(7,4))
            plt.bar([p - width/2 for p in x], non_vals, width=width, label='non-inclusive')
            plt.bar([p + width/2 for p in x], ex_vals, width=width, label='exclusive')
            plt.xticks(x, labels)
            plt.ylabel("MPKI")
            plt.title(f"Q2: MPKI Comparison — {t}")
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            out = os.path.join(output_dir, f"q2_mpki_cmp_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

        # Q3: Exclusive prefetcher study: generate two speedup curves
        # Find exclusive_prefetcher runs (exclusive_table32/64/128)
        ex_pref_variants = [('exclusive_table32', 32), ('exclusive_table64', 64), ('exclusive_table128', 128)]
        xs_ex, ys_nonbase, ys_exbase = [], [], []
        for vname, vsz in ex_pref_variants:
            r = sub[sub['variant'] == vname]
            if r.empty: continue
            ipc_v = float(r['ipc'].iloc[0])
            xs_ex.append(vsz)
            # speedup vs non-inclusive baseline
            if base_non_ipc: ys_nonbase.append(ipc_v / base_non_ipc)
            else: ys_nonbase.append(None)
            # speedup vs exclusive baseline
            if base_excl_ipc: ys_exbase.append(ipc_v / base_excl_ipc)
            else: ys_exbase.append(None)

        # plot Q3 curve vs non-inclusive baseline
        if xs_ex and any(y is not None for y in ys_nonbase):
            plt.figure(figsize=(6,4))
            plt.plot(xs_ex, ys_nonbase, marker='o')
            plt.title(f"Q3 (exclusive-pref): Speedup vs Table Size — baseline=non-inclusive — {t}")
            plt.xlabel("Table size (entries)")
            plt.ylabel("Speedup")
            plt.grid(True); plt.axhline(1.0, color='gray', linestyle='--')
            out = os.path.join(output_dir, f"q3_speedup_noninc_baseline_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

        # plot Q3 curve vs exclusive baseline
        if xs_ex and any(y is not None for y in ys_exbase):
            plt.figure(figsize=(6,4))
            plt.plot(xs_ex, ys_exbase, marker='o')
            plt.title(f"Q3 (exclusive-pref): Speedup vs Table Size — baseline=exclusive — {t}")
            plt.xlabel("Table size (entries)")
            plt.ylabel("Speedup")
            plt.grid(True); plt.axhline(1.0, color='gray', linestyle='--')
            out = os.path.join(output_dir, f"q3_speedup_excl_baseline_{t}.png")
            plt.savefig(out); plt.close()
            print(f"Saved {out}")

    print("\nAll done. CSV and PNGs saved to output directory.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='./output', help='Path to output folder')
    parser.add_argument('--save-csv', default='outputs_parsed_all.csv', help='CSV output filename')
    args = parser.parse_args()
    main(args.output_dir, args.save_csv)
