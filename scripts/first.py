import matplotlib.pyplot as plt

table_sizes = [32, 64, 128]
speedups = [1.066, 1.100, 1.125]  # replace with your results

plt.plot(table_sizes, speedups, marker='o')
plt.xlabel("Table Size (entries)")
plt.ylabel("Speedup over Baseline")
plt.title("Region-Based Offset Prefetcher Speedup")
plt.grid(True)
plt.show()
