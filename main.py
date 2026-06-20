"""
main.py - Entry point for the CPU Scheduling Simulator.

Usage
-----
    python main.py            Launch the graphical interface (default).
    python main.py --cli      Run a text-only demonstration in the terminal
                              (useful when there is no display, or for the
                              demo video's "under the hood" explanation).

The command-line mode prints, for every algorithm, the per-process table, an
ASCII Gantt chart and the average statistics.
"""

from __future__ import annotations

import sys

import scheduler
from scheduler import Process, IDLE_LABEL


# ---------------------------------------------------------------------------
# Text rendering used by the --cli mode
# ---------------------------------------------------------------------------
def format_table(result) -> str:
    """Return the per-process metrics as an aligned text table."""
    header = ("Process", "Arrival", "Burst", "Priority", "Start",
              "Completion", "Waiting", "Turnaround", "Response")
    rows = [header]
    for m in result.metrics:
        rows.append((m.pid, str(m.arrival), str(m.burst), str(m.priority),
                     str(m.start), str(m.completion), str(m.waiting),
                     str(m.turnaround), str(m.response)))
    widths = [max(len(r[c]) for r in rows) for c in range(len(header))]
    lines = []
    for i, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[c])
                               for c, cell in enumerate(row)))
        if i == 0:
            lines.append("  ".join("-" * widths[c] for c in range(len(header))))
    return "\n".join(lines)


def format_gantt(result) -> str:
    """Return a two-line ASCII Gantt chart with a time axis underneath."""
    if not result.gantt:
        return "(empty)"
    top, axis = "", ""
    for label, start, end in result.gantt:
        width = max(len(label) + 2, 2 * (end - start) + 1, 5)
        text = "Idle" if label == IDLE_LABEL else label
        top += "|" + text.center(width)
        axis += str(start).ljust(width + 1)
    top += "|"
    axis += str(result.gantt[-1][2])
    bar = "+" + "+".join("-" * (len(seg) - 1)
                         for seg in top.split("|")[1:-1]) + "+"
    return f"{bar}\n{top}\n{bar}\n{axis}"


def print_results(results) -> None:
    for result in results:
        print("=" * 70)
        title = result.algorithm
        if result.quantum is not None:
            title += f"   (time quantum = {result.quantum})"
        print(title)
        print("=" * 70)
        print(format_table(result))
        print()
        print("Gantt chart:")
        print(format_gantt(result))
        print()
        print(f"Execution order      : {' -> '.join(result.execution_order)}")
        print(f"Average waiting time : {result.avg_waiting:.2f}")
        print(f"Average turnaround   : {result.avg_turnaround:.2f}")
        print(f"Average response     : {result.avg_response:.2f}")
        print(f"CPU utilization      : {result.cpu_utilization:.1f}%")
        print(f"Throughput           : {result.throughput:.3f} processes/unit")
        print()


def run_cli() -> None:
    """Demonstrate every algorithm on one sample workload."""
    workload = [
        Process("P1", arrival=0, burst=5, priority=2),
        Process("P2", arrival=1, burst=3, priority=1),
        Process("P3", arrival=2, burst=8, priority=4),
        Process("P4", arrival=3, burst=6, priority=3),
    ]

    print("\nCPU SCHEDULING SIMULATOR - command-line demonstration")
    print("Sample workload (priority: smaller number = higher priority):\n")
    print(f"  {'Process':<9}{'Arrival':<9}{'Burst':<8}{'Priority'}")
    for p in workload:
        print(f"  {p.pid:<9}{p.arrival:<9}{p.burst:<8}{p.priority}")
    print()

    quantum = 2
    # *f: Fixed double call issue (from 12 simulation call to 6)
    results = scheduler.compare_all(workload, quantum)
    print_results(results)
    # Side-by-side comparison summary.
    print("=" * 70)
    print("COMPARISON SUMMARY (lower waiting/turnaround is better)")
    print("=" * 70)
    header = f"{'Algorithm':<26}{'AvgWait':>9}{'AvgTAT':>9}{'AvgResp':>9}{'CPU%':>8}"
    print(header)
    print("-" * len(header))
    best = min(results, key=lambda r: r.avg_waiting)
    for r in results:
        mark = "  <-- lowest waiting" if r is best else ""
        print(f"{r.algorithm:<26}{r.avg_waiting:>9.2f}{r.avg_turnaround:>9.2f}"
              f"{r.avg_response:>9.2f}{r.cpu_utilization:>8.1f}{mark}")
    print()


def main() -> None:
    if "--cli" in sys.argv:
        run_cli()
        return
    try:
        import gui
    except Exception as exc:  # pragma: no cover - depends on display/backend
        print(f"Could not start the graphical interface: {exc}")
        print("Falling back to the command-line demo (run with --cli "
              "to do this on purpose).\n")
        run_cli()
        return
    gui.launch()


if __name__ == "__main__":
    main()
