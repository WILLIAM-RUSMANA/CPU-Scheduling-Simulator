"""
scheduler.py - Core CPU scheduling engine.

This module contains the pure scheduling logic with no user-interface code, so
it can be tested on its own (see test_scheduler.py) and reused by both the GUI
(gui.py) and the command-line demo (main.py).

Conventions used throughout this project
-----------------------------------------
* Time is measured in integer "time units" starting at 0.
* Priority uses the common textbook rule: a SMALLER number means a HIGHER
  priority (so priority 1 runs before priority 5).
* When the CPU would otherwise sit idle (no process has arrived yet) the gap is
  recorded in the Gantt chart as an "Idle" block but is ignored when averaging.
* Ties are broken first by arrival time and then by process id, which keeps
  every algorithm deterministic and easy to reason about.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import random

# Label used for the idle blocks that appear in a Gantt chart.
IDLE_LABEL = "Idle"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class Process:
    """A single process supplied by the user.

    Attributes
    ----------
    pid       : process identifier, e.g. "P1"
    arrival   : the time unit at which the process enters the ready queue
    burst     : total CPU time the process needs to finish
    priority  : scheduling priority (smaller = more important)
    """

    pid: str
    arrival: int
    burst: int
    priority: int = 0

    def __post_init__(self) -> None:
        # Light validation so mistakes fail loudly instead of producing
        # nonsense schedules later on.
        if self.arrival < 0:
            raise ValueError(f"{self.pid}: arrival time cannot be negative")
        if self.burst <= 0:
            raise ValueError(f"{self.pid}: burst time must be greater than 0")


@dataclass
class ProcessMetrics:
    """The per-process results produced after a schedule is simulated."""

    pid: str
    arrival: int
    burst: int
    priority: int
    start: int          # time the process first got the CPU
    completion: int     # time the process finished
    turnaround: int     # completion - arrival
    waiting: int        # turnaround - burst
    response: int       # start - arrival


@dataclass
class ScheduleResult:
    """Everything we know about one completed simulation.

    ``gantt`` is a list of ``(label, start, end)`` tuples in execution order,
    where ``label`` is a process id or :data:`IDLE_LABEL`.
    """

    algorithm: str
    gantt: list[tuple[str, int, int]]
    metrics: list[ProcessMetrics]
    quantum: int | None = None  # only meaningful for Round Robin

    # -- average statistics -------------------------------------------------
    @property
    def avg_waiting(self) -> float:
        return _mean(m.waiting for m in self.metrics)

    @property
    def avg_turnaround(self) -> float:
        return _mean(m.turnaround for m in self.metrics)

    @property
    def avg_response(self) -> float:
        return _mean(m.response for m in self.metrics)

    # -- overall statistics -------------------------------------------------
    @property
    def total_span(self) -> int:
        """Wall-clock length of the whole schedule (including idle gaps)."""
        if not self.gantt:
            return 0
        return self.gantt[-1][2] - self.gantt[0][1]

    @property
    def cpu_utilization(self) -> float:
        """Percentage of the schedule the CPU was actually doing work."""
        if not self.gantt:
            return 0.0
        busy = sum(end - start for label, start, end in self.gantt
                   if label != IDLE_LABEL)
        span = self.total_span
        return (busy / span * 100.0) if span else 0.0

    @property
    def throughput(self) -> float:
        """Processes completed per time unit."""
        span = self.total_span
        return (len(self.metrics) / span) if span else 0.0

    @property
    def execution_order(self) -> list[str]:
        """The order in which processes (ignoring idle) first/again ran."""
        return [label for label, _, _ in self.gantt if label != IDLE_LABEL]


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Shared helpers used by the individual algorithms
# ---------------------------------------------------------------------------
def _merge_segments(gantt):
    """Join touching blocks that belong to the same process.

    The preemptive simulation can emit two adjacent slices for the same
    process (for example when a newly arrived process does not actually
    preempt the running one). Merging keeps the Gantt chart tidy.
    """
    merged: list[tuple[str, int, int]] = []
    for label, start, end in gantt:
        if merged and merged[-1][0] == label and merged[-1][2] == start:
            prev_label, prev_start, _ = merged[-1]
            merged[-1] = (prev_label, prev_start, end)
        else:
            merged.append((label, start, end))
    return merged


def _build_result(algorithm, processes, gantt, first_start, completion,
                  quantum=None):
    """Turn raw simulation bookkeeping into a :class:`ScheduleResult`.

    ``first_start`` maps pid -> the time the process first ran; ``completion``
    maps pid -> the time it finished. Metrics are returned in the same order
    the processes were supplied so the results table matches the input table.
    """
    metrics = []
    for p in processes:
        start = first_start[p.pid]
        finish = completion[p.pid]
        turnaround = finish - p.arrival
        waiting = turnaround - p.burst
        response = start - p.arrival
        metrics.append(ProcessMetrics(
            pid=p.pid, arrival=p.arrival, burst=p.burst, priority=p.priority,
            start=start, completion=finish, turnaround=turnaround,
            waiting=waiting, response=response,
        ))
    return ScheduleResult(algorithm, gantt, metrics, quantum)


def _validate(processes):
    if not processes:
        raise ValueError("Add at least one process before running a schedule.")
    pids = [p.pid for p in processes]
    if len(set(pids)) != len(pids):
        raise ValueError("Process ids must be unique.")


# ---------------------------------------------------------------------------
# Non-preemptive algorithms (FCFS, SJF, Priority)
# ---------------------------------------------------------------------------
def _simulate_non_preemptive(processes, select_key, algorithm):
    """Generic non-preemptive scheduler.

    At every point the CPU is free we look at the processes that have already
    arrived and pick the "best" one according to ``select_key``. Because the
    job is never interrupted, the three required non-preemptive policies differ
    only in that key:

    * FCFS     -> earliest arrival
    * SJF      -> shortest burst
    * Priority -> smallest priority number
    """
    _validate(processes)
    procs = list(processes)
    done: set[str] = set()
    time = 0
    gantt: list[tuple[str, int, int]] = []
    first_start: dict[str, int] = {}
    completion: dict[str, int] = {}

    while len(done) < len(procs):
        ready = [p for p in procs if p.arrival <= time and p.pid not in done]
        if not ready:
            # CPU is idle: jump forward to the next arrival instead of
            # busy-waiting one unit at a time.
            next_arrival = min(p.arrival for p in procs if p.pid not in done)
            gantt.append((IDLE_LABEL, time, next_arrival))
            time = next_arrival
            continue

        chosen = min(ready, key=select_key)
        start = time
        time += chosen.burst
        first_start[chosen.pid] = start
        completion[chosen.pid] = time
        gantt.append((chosen.pid, start, time))
        done.add(chosen.pid)

    return _build_result(algorithm, procs, gantt, first_start, completion)


def fcfs(processes):
    """First Come First Serve: run jobs in the order they arrive."""
    return _simulate_non_preemptive(
        processes,
        select_key=lambda p: (p.arrival, p.pid),
        algorithm="FCFS",
    )


def sjf(processes):
    """Shortest Job First (non-preemptive): pick the shortest ready job."""
    return _simulate_non_preemptive(
        processes,
        select_key=lambda p: (p.burst, p.arrival, p.pid),
        algorithm="SJF (Non-preemptive)",
    )


def priority_scheduling(processes):
    """Priority scheduling (non-preemptive): smallest priority number wins."""
    return _simulate_non_preemptive(
        processes,
        select_key=lambda p: (p.priority, p.arrival, p.pid),
        algorithm="Priority (Non-preemptive)",
    )


# ---------------------------------------------------------------------------
# Preemptive algorithms (SRTF, preemptive Priority)
# ---------------------------------------------------------------------------
def _simulate_preemptive(processes, select_key, algorithm):
    """Generic preemptive scheduler driven by arrival events.

    Between two consecutive arrivals the ready set never changes and the
    running process can only get "better" (its remaining time keeps shrinking),
    so it stays the chosen one until it either finishes or the next process
    arrives. That lets us advance time in big jumps to the next event instead of
    one unit at a time, which is both faster and exactly equivalent.

    ``select_key(process, remaining)`` returns the comparison key:
    * SRTF              -> smallest remaining time
    * Priority (preempt)-> smallest priority number
    """
    _validate(processes)
    procs = list(processes)
    remaining = {p.pid: p.burst for p in procs}
    completed = 0
    time = 0
    gantt: list[tuple[str, int, int]] = []
    first_start: dict[str, int] = {}
    completion: dict[str, int] = {}

    while completed < len(procs):
        ready = [p for p in procs if p.arrival <= time and remaining[p.pid] > 0]
        if not ready:
            next_arrival = min(p.arrival for p in procs if remaining[p.pid] > 0)
            gantt.append((IDLE_LABEL, time, next_arrival))
            time = next_arrival
            continue

        chosen = min(ready, key=lambda p: select_key(p, remaining))
        if chosen.pid not in first_start:
            first_start[chosen.pid] = time

        # Run until either this process finishes or the next process arrives,
        # because that is the only moment the decision could change.
        future_arrivals = [p.arrival for p in procs
                           if p.arrival > time and remaining[p.pid] > 0]
        next_event = min(future_arrivals) if future_arrivals else float("inf")
        run_for = min(remaining[chosen.pid], next_event - time)

        gantt.append((chosen.pid, time, time + run_for))
        remaining[chosen.pid] -= run_for
        time += run_for
        if remaining[chosen.pid] == 0:
            completion[chosen.pid] = time
            completed += 1

    gantt = _merge_segments(gantt)
    return _build_result(algorithm, procs, gantt, first_start, completion)


def srtf(processes):
    """Shortest Remaining Time First (preemptive SJF)."""
    return _simulate_preemptive(
        processes,
        select_key=lambda p, remaining: (remaining[p.pid], p.arrival, p.pid),
        algorithm="SRTF (Preemptive SJF)",
    )


def priority_preemptive(processes):
    """Preemptive priority scheduling (smallest priority number wins)."""
    return _simulate_preemptive(
        processes,
        select_key=lambda p, remaining: (p.priority, p.arrival, p.pid),
        algorithm="Priority (Preemptive)",
    )


# ---------------------------------------------------------------------------
# Round Robin
# ---------------------------------------------------------------------------
def round_robin(processes, quantum):
    """Round Robin scheduling with a fixed time quantum.

    Each process runs for at most ``quantum`` units before being sent to the
    back of the ready queue. Following the usual textbook convention, processes
    that arrive while a slice is running (including exactly at the moment it
    ends) are queued *before* the process that was just preempted.
    """
    _validate(processes)
    if quantum is None or quantum <= 0:
        raise ValueError("Round Robin requires a time quantum of at least 1.")

    # Sort a copy by arrival so we can feed processes into the queue in order.
    procs = sorted(processes, key=lambda p: (p.arrival, p.pid))
    remaining = {p.pid: p.burst for p in procs}
    time = 0
    queue: deque[Process] = deque()
    gantt: list[tuple[str, int, int]] = []
    first_start: dict[str, int] = {}
    completion: dict[str, int] = {}
    next_idx = 0  # index of the next not-yet-queued process in ``procs``

    def enqueue_arrivals(up_to):
        """Add every process that has arrived by ``up_to`` to the queue."""
        nonlocal next_idx
        while next_idx < len(procs) and procs[next_idx].arrival <= up_to:
            queue.append(procs[next_idx])
            next_idx += 1

    enqueue_arrivals(time)
    while queue or next_idx < len(procs):
        if not queue:
            # Nothing ready yet: fast-forward to the next arrival.
            next_arrival = procs[next_idx].arrival
            gantt.append((IDLE_LABEL, time, next_arrival))
            time = next_arrival
            enqueue_arrivals(time)
            continue

        current = queue.popleft()
        if current.pid not in first_start:
            first_start[current.pid] = time

        run_for = min(quantum, remaining[current.pid])
        start = time
        time += run_for
        remaining[current.pid] -= run_for
        gantt.append((current.pid, start, time))

        # Queue everyone who arrived during this slice before re-queuing the
        # process we just ran (standard Round Robin ordering).
        enqueue_arrivals(time)
        if remaining[current.pid] > 0:
            queue.append(current)
        else:
            completion[current.pid] = time

    gantt = _merge_segments(gantt)
    return _build_result("Round Robin", procs, gantt, first_start,
                         completion, quantum=quantum)


# ---------------------------------------------------------------------------
# Public dispatch table + helpers
# ---------------------------------------------------------------------------
# Maps a human-readable name to a callable. Round Robin needs a quantum, which
# is why callers should go through ``run_algorithm`` rather than calling these
# directly when a quantum may be involved.
ALGORITHMS = {
    "FCFS": fcfs,
    "SJF (Non-preemptive)": sjf,
    "SRTF (Preemptive SJF)": srtf,
    "Round Robin": round_robin,
    "Priority (Non-preemptive)": priority_scheduling,
    "Priority (Preemptive)": priority_preemptive,
}


def run_algorithm(name, processes, quantum=4):
    """Run a named algorithm, supplying ``quantum`` only to Round Robin."""
    if name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {name!r}")
    if name == "Round Robin":
        return round_robin(processes, quantum)
    return ALGORITHMS[name](processes)


def compare_all(processes, quantum=4):
    """Run every algorithm and return a list of results for comparison."""
    return [run_algorithm(name, processes, quantum) for name in ALGORITHMS]


def generate_random_workload(count=5, max_arrival=10, max_burst=10,
                             max_priority=5, seed=None):
    """Create a list of random :class:`Process` objects for quick testing."""
    rng = random.Random(seed)
    workload = []
    for i in range(1, count + 1):
        workload.append(Process(
            pid=f"P{i}",
            arrival=rng.randint(0, max_arrival),
            burst=rng.randint(1, max_burst),
            priority=rng.randint(1, max_priority),
        ))
    return workload
