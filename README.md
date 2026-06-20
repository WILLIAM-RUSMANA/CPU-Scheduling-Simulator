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

## Scheduling Algorithm Explanation
First Come First Serve, abbreviated as FCFS, is a non-preemptive scheduling algorithm. Processes are executed in the exact order they arrive in the ready queue, making it the simplest scheduling technique, essentially operating as a First-In, First-Out queue. In the simulator, the FCFS algorithm processes all available jobs at the current time, sorting the ready queue primarily by arrival time, with ties broken by process ID to maintain determinism. Once a process starts executing, it runs to completion without interruption. The primary advantage of FCFS is its ease of implementation, but it suffers from the convoy effect, where short processes may be delayed behind a single long process, leading to poor average waiting and turnaround times. Being non-preemptive makes it unsuitable for time-sharing systems where responsiveness is important.

Shortest Job First, or SJF, is also a non-preemptive algorithm, though its preemptive version, Shortest Remaining Time First, is covered as an advanced feature. When the CPU becomes available, the process with the smallest total burst time is selected from the ready queue. In the implementation, at each scheduling decision point when a process completes, the ready queue is sorted by remaining burst time, with the shortest being selected, and ties are broken first by arrival time and then by process ID. SJF is optimal for minimizing average waiting time for a given set of processes in a batch environment. However, it requires prior knowledge of the burst time of each process, which is difficult to predict in practice. Furthermore, it can lead to starvation, where longer processes may be indefinitely delayed by a continuous stream of shorter jobs.

Round Robin, abbreviated as RR, is a preemptive algorithm designed for time-sharing systems. Each process receives a small, fixed unit of CPU time called a time quantum. Processes are maintained in a circular ready queue, and the scheduler allocates the CPU to the first process in the queue for one quantum. If the process does not complete within that quantum, it is preempted and moved to the back of the queue. In the simulator, the user defines the time quantum, and the algorithm simulates time in discrete units, maintaining a ready queue that is updated as new processes arrive. Processes that arrive during an active time slice are queued before the process that is being preempted, following standard Round Robin convention. If the CPU is idle, time advances to the next arrival. Round Robin ensures responsiveness, as every process gets a chance to run within a bounded time. However, its performance is highly dependent on the time quantum; a very large quantum makes it similar to FCFS, while a very small quantum incurs high context-switching overhead.

Priority Scheduling, in its non-preemptive form, allocates the CPU to the process with the highest priority, represented by the smallest priority number. A process that has been allocated the CPU runs to completion unless a higher-priority process arrives, though this scenario only applies to the preemptive version. In the implementation, at each scheduling decision point, the ready queue is sorted by priority number, and the process with the smallest number is selected, with ties broken by arrival time and then by process ID. This algorithm is suitable for systems with varying task importance, such as giving system processes higher priority than user processes. Its major disadvantage is the potential for starvation, where low-priority processes are indefinitely postponed. This issue can be mitigated by a technique called aging, which gradually increases the priority of waiting processes over time.


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
