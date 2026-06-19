# CPU Scheduling Simulator

A Python simulator for the four required CPU scheduling algorithms plus several
extensions, with a Tkinter GUI, Matplotlib Gantt charts, automatic algorithm
comparison and CSV/PNG export.

## Dependencies

* **Python 3.x** (developed and tested on 3.14)
* **Tkinter** — bundled with the standard Python installer on Windows/macOS;
  on Debian/Ubuntu install with `sudo apt install python3-tk`
* **Matplotlib** — install with:

  ```bash
  pip install -r requirements.txt
  ```

No other third-party packages are needed (CSV export uses the standard library,
so Pandas is **not** required).

## How to run

```bash
# Graphical interface (default)
python main.py

# Text-only demonstration in the terminal (no display needed)
python main.py --cli

# Verify the scheduling engine against textbook examples
python test_scheduler.py
```

## Using the GUI

1. **Add processes** — type a Process ID, Arrival Time, Burst Time and Priority,
   then click **Add**. Select a row to **Update** or **Remove** it. The window
   starts with a small sample workload.
2. **Random Workload** generates five random processes for quick testing.
3. **Pick an algorithm** from the dropdown. The **Time Quantum** field is only
   used by Round Robin (it is disabled for the others).
4. **Run Selected Algorithm** draws the Gantt chart and fills the per-process
   metrics table with Start, Completion, Waiting, Turnaround and Response times,
   plus the averages, CPU utilisation and throughput.
5. **Run All Algorithms** runs every algorithm on the same workload and fills
   two tabs: the **Comparison** tab (a grouped bar chart and a comparison table,
   with the lowest average waiting time highlighted in green) and the **All
   Gantt Charts** tab (all six schedules stacked on one shared time axis, where
   each process keeps the same colour across every chart for easy comparison).
6. **Export Results (CSV)** saves the current table and averages; **Save Chart
   (PNG)** saves the chart on the visible tab.

## Files

| File                 | Responsibility                                             |
|----------------------|------------------------------------------------------------|
| `scheduler.py`       | Pure scheduling engine: process model, all algorithms, metrics. No UI. |
| `gui.py`             | Tkinter interface with embedded Matplotlib charts.         |
| `main.py`            | Entry point; launches the GUI or the `--cli` demo.         |
| `test_scheduler.py`  | Automated correctness checks against known textbook answers.|

## Algorithms implemented

| Algorithm | Type | Selection rule |
|-----------|------|----------------|
| **FCFS** | Non-preemptive | Earliest arrival time |
| **SJF** | Non-preemptive | Shortest burst time |
| **SRTF** | Preemptive | Shortest *remaining* time (preemptive SJF) — *Part 2* |
| **Round Robin** | Preemptive | Fixed time-quantum rotation |
| **Priority** | Non-preemptive | Smallest priority number |
| **Priority (Preemptive)** | Preemptive | Smallest priority number, re-checked on each arrival — *Part 2 extra* |

### Conventions
* Time is measured in integer units starting at 0.
* **Priority: a smaller number means higher priority** (priority 1 beats 5).
* Ties are broken by arrival time, then by process id, so results are
  deterministic.
* When no process has arrived yet the CPU is **Idle**; idle gaps appear in the
  Gantt chart but are excluded from the averages.
* Round Robin follows the standard convention: processes that arrive while a
  time slice is running are queued *before* the just-preempted process.

## How the requirements are covered

**Part 1 (core):** FCFS, SJF, Round Robin and Priority; user input of Process
ID / Arrival / Burst / Priority; execution order, waiting time, turnaround time
and their averages; a Gantt chart visualisation.

**Part 2 (advanced):** the project includes **six** of the optional features —
a full GUI, random workload generation, automatic algorithm comparison, SRTF,
performance-statistics visualisation (bar charts), and CSV/PNG export.

## Design notes

The scheduler is deliberately split from the interface so the logic can be
tested on its own. The three non-preemptive policies share one routine that
only differs by a "which ready process is best" key, and SRTF and preemptive
priority share an event-driven routine that advances time to the next arrival
instead of stepping one unit at a time. The GUI keeps a single list of
`Process` objects as the source of truth and rebuilds the on-screen table from
it after every change.

## Academic-integrity note

This project was developed with AI assistance. Before submitting you **must**
read through every file and make sure you can explain it, since the assignment
requires that you understand all submitted code and disclose AI usage honestly
in your reflection report. The `test_scheduler.py` file is a good starting
point for understanding what each algorithm is expected to produce.
