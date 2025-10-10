import pandas as pd
import matplotlib.pyplot as plt
import os

# -------------------------------------------------------------------
# Load parsed data
# -------------------------------------------------------------------
df = pd.read_csv("outputs_parsed_all.csv")

# Create output dir for plots
os.makedirs("plots", exist_ok=True)

# Helper function: calculate speedup
def calc_speedup(ipc, baseline_ipc):
    return ipc / baseline_ipc if baseline_ipc != 0 else 0

# Common plotting helper
def plot_bar(x, y, ylabel, title, filename, baseline_value=None, baseline_label=None, annotate=False):
    plt.figure(figsize=(7, 5))
    bars = plt.bar(x, y, color="steelblue", edgecolor="black")
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xticks(rotation=20)

    # Add annotations above bars
    if annotate:
        for bar in bars:
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{bar.get_height():.2f}",
                     ha='center', va='bottom', fontsize=8)

    # Add horizontal red line for baseline reference
    if baseline_value is not None:
        plt.axhline(y=baseline_value, color='red', linestyle='--', linewidth=1.5,
                    label=f'{baseline_label or "Baseline"} = {baseline_value:.2f}')
        plt.legend()

    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


# -------------------------------------------------------------------
# Q1: Offset Prefetcher (Non-Inclusive) — compare all table sizes
# -------------------------------------------------------------------
print("📊 Generating Q1 plots...")
q1_traces = sorted([t for t in df['trace_folder'].unique() if t.startswith("1st_trace")])

for trace in q1_traces:
    sub = df[df['trace_folder'] == trace]
    base = sub[sub['variant'] == "baseline_noninc"]
    if base.empty:
        continue
    base_ipc = base['ipc'].values[0]
    base_mpki = base['l2_mpki'].values[0]

    variants = ["baseline_noninc", "table32", "table64", "table128"]
    sub = sub[sub['variant'].isin(variants)]

    # Speedup vs baseline
    speedups = [calc_speedup(ipc, base_ipc) for ipc in sub['ipc']]
    plot_bar(sub['variant'], speedups, "Speedup (IPC / Baseline IPC)",
             f"Q1 Speedup — {trace}",
             f"plots/q1_speedup_{trace}.png",
             baseline_value=1.0, baseline_label="Non-Inclusive", annotate=True)

    # MPKI comparison
    plot_bar(sub['variant'], sub['l2_mpki'], "L2 MPKI",
             f"Q1 L2 MPKI — {trace}",
             f"plots/q1_mpki_{trace}.png",
             baseline_value=base_mpki, baseline_label="Baseline MPKI", annotate=True)

    # IPC comparison
    plot_bar(sub['variant'], sub['ipc'], "IPC",
             f"Q1 IPC — {trace}",
             f"plots/q1_ipc_{trace}.png",
             baseline_value=base_ipc, baseline_label="Baseline IPC", annotate=True)


# -------------------------------------------------------------------
# Q2: Exclusive vs Non-Inclusive Comparison
# -------------------------------------------------------------------
print("📊 Generating Q2 plots...")
q2_traces = sorted([t for t in df['trace_folder'].unique() if t.startswith("2nd_trace")])

for trace in q2_traces:
    sub = df[df['trace_folder'] == trace]
    variants = ["baseline_noninc", "baseline_exclusive"]
    sub = sub[sub['variant'].isin(variants)]

    if sub.empty:
        continue

    base_ipc = sub[sub['variant'] == "baseline_noninc"]['ipc'].values[0]
    base_mpki = sub[sub['variant'] == "baseline_noninc"]['l2_mpki'].values[0]
    excl_ipc = sub[sub['variant'] == "baseline_exclusive"]['ipc'].values[0]

    # IPC comparison
    plot_bar(sub['variant'], sub['ipc'], "IPC",
             f"Q2 IPC Comparison — {trace}",
             f"plots/q2_ipc_cmp_{trace}.png",
             baseline_value=base_ipc, baseline_label="Non-Inclusive IPC", annotate=True)

    # MPKI comparison
    plot_bar(sub['variant'], sub['l2_mpki'], "L2 MPKI",
             f"Q2 L2 MPKI Comparison — {trace}",
             f"plots/q2_mpki_cmp_{trace}.png",
             baseline_value=base_mpki, baseline_label="Non-Inclusive MPKI", annotate=True)

    # Speedup of Exclusive vs Non-Inclusive
    speedup = calc_speedup(excl_ipc, base_ipc)
    plot_bar(["Exclusive vs Non-Inclusive"], [speedup], "Speedup",
             f"Q2 Speedup — {trace}",
             f"plots/q2_speedup_{trace}.png",
             baseline_value=1.0, baseline_label="Non-Inclusive", annotate=True)


# -------------------------------------------------------------------
# Q3: Exclusive Prefetcher — compare with both baselines
# -------------------------------------------------------------------
print("📊 Generating Q3 plots...")
q3_traces = sorted([t for t in df['trace_folder'].unique() if t.startswith("3rd_trace")])

for trace in q3_traces:
    sub = df[df['trace_folder'] == trace]
    if sub.empty:
        continue

    base_noninc_ipc = sub[sub['variant'] == "baseline_noninc"]['ipc'].values[0]
    base_excl_ipc = sub[sub['variant'] == "baseline_exclusive"]['ipc'].values[0]
    base_noninc_mpki = sub[sub['variant'] == "baseline_noninc"]['l2_mpki'].values[0]
    base_excl_mpki = sub[sub['variant'] == "baseline_exclusive"]['l2_mpki'].values[0]

    pref_sub = sub[sub['variant'].str.startswith("table")]

    # Speedup vs Non-Inclusive Baseline
    speedups_noninc = [calc_speedup(ipc, base_noninc_ipc) for ipc in pref_sub['ipc']]
    plot_bar(pref_sub['variant'], speedups_noninc, "Speedup (vs Non-Inclusive)",
             f"Q3 Speedup vs Non-Inclusive Baseline — {trace}",
             f"plots/q3_speedup_noninc_{trace}.png",
             baseline_value=1.0, baseline_label="Non-Inclusive", annotate=True)

    # Speedup vs Exclusive Baseline
    speedups_excl = [calc_speedup(ipc, base_excl_ipc) for ipc in pref_sub['ipc']]
    plot_bar(pref_sub['variant'], speedups_excl, "Speedup (vs Exclusive)",
             f"Q3 Speedup vs Exclusive Baseline — {trace}",
             f"plots/q3_speedup_excl_{trace}.png",
             baseline_value=1.0, baseline_label="Exclusive", annotate=True)

    # MPKI comparison
    plot_bar(pref_sub['variant'], pref_sub['l2_mpki'], "L2 MPKI",
             f"Q3 L2 MPKI — {trace}",
             f"plots/q3_mpki_{trace}.png",
             baseline_value=base_excl_mpki, baseline_label="Exclusive MPKI", annotate=True)

    # IPC comparison
    plot_bar(pref_sub['variant'], pref_sub['ipc'], "IPC",
             f"Q3 IPC — {trace}",
             f"plots/q3_ipc_{trace}.png",
             baseline_value=base_excl_ipc, baseline_label="Exclusive IPC", annotate=True)

print("✅ All plots generated in 'plots/' folder successfully with red baseline lines!")
