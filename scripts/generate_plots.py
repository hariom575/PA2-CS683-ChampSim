import pandas as pd
import matplotlib.pyplot as plt
import os

# Load parsed data
df = pd.read_csv("outputs_parsed_all.csv")

# Create output dir for plots
os.makedirs("plots", exist_ok=True)

# Helper function: calculate speedup
def calc_speedup(ipc, baseline_ipc):
    return ipc / baseline_ipc

# ---------------- Q1: Non-inclusive Prefetcher Speedup & MPKI ----------------
q1_traces = [t for t in df['trace_folder'].unique() if t.startswith("1st_trace")]
for trace in q1_traces:
    sub = df[df['trace_folder'] == trace]
    base_ipc = sub[sub['variant'] == "baseline_noninc"]['ipc'].values[0]
    base_mpki = sub[sub['variant'] == "baseline_noninc"]['l2_mpki'].values[0]

    variants = ["baseline_noninc", "table32", "table64", "table128"]
    sub = sub[sub['variant'].isin(variants)]

    # Speedup
    speedups = [calc_speedup(ipc, base_ipc) for ipc in sub['ipc']]
    plt.bar(sub['variant'], speedups)
    plt.title(f"Q1 Speedup ({trace})")
    plt.ylabel("Speedup (IPC / Baseline IPC)")
    plt.savefig(f"plots/q1_speedup_{trace}.png")
    plt.close()

    # MPKI
    mpkis = sub['l2_mpki']
    plt.bar(sub['variant'], mpkis)
    plt.title(f"Q1 L2 MPKI ({trace})")
    plt.ylabel("L2 MPKI")
    plt.savefig(f"plots/q1_mpki_{trace}.png")
    plt.close()

# ---------------- Q2: IPC & MPKI Comparison (Exclusive vs Non-Inclusive) ----------------
q2_traces = [t for t in df['trace_folder'].unique() if t.startswith("2nd_trace")]
for trace in q2_traces:
    sub = df[df['trace_folder'] == trace]
    variants = ["baseline_noninc", "baseline_exclusive"]
    sub = sub[sub['variant'].isin(variants)]

    # IPC comparison
    plt.bar(sub['variant'], sub['ipc'])
    plt.title(f"Q2 IPC Comparison ({trace})")
    plt.ylabel("IPC")
    plt.savefig(f"plots/q2_ipc_cmp_{trace}.png")
    plt.close()

    # MPKI comparison
    plt.bar(sub['variant'], sub['l2_mpki'])
    plt.title(f"Q2 L2 MPKI Comparison ({trace})")
    plt.ylabel("L2 MPKI")
    plt.savefig(f"plots/q2_mpki_cmp_{trace}.png")
    plt.close()

# ---------------- Q3: Exclusive Prefetcher Speedups ----------------
q3_traces = [t for t in df['trace_folder'].unique() if t.startswith("3rd_trace")]
for trace in q3_traces:
    sub = df[df['trace_folder'] == trace]
    base_noninc = sub[sub['variant'] == "baseline_noninc"]['ipc'].values[0]
    base_excl = sub[sub['variant'] == "baseline_exclusive"]['ipc'].values[0]

    # Non-inclusive baseline speedup
    sub_pref = sub[sub['variant'].str.startswith("table")]
    speedups_noninc = [calc_speedup(ipc, base_noninc) for ipc in sub_pref['ipc']]
    plt.bar(sub_pref['variant'], speedups_noninc)
    plt.title(f"Q3 Speedup vs Non-Inclusive Baseline ({trace})")
    plt.ylabel("Speedup")
    plt.savefig(f"plots/q3_speedup_noninc_baseline_{trace}.png")
    plt.close()

    # Exclusive baseline speedup
    speedups_excl = [calc_speedup(ipc, base_excl) for ipc in sub_pref['ipc']]
    plt.bar(sub_pref['variant'], speedups_excl)
    plt.title(f"Q3 Speedup vs Exclusive Baseline ({trace})")
    plt.ylabel("Speedup")
    plt.savefig(f"plots/q3_speedup_excl_baseline_{trace}.png")
    plt.close()

print("✅ All plots generated in 'plots/' folder.")
