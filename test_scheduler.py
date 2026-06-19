"""
test_scheduler.py - Correctness checks for the scheduling engine.

Each test uses a small example whose answer can be worked out by hand (several
are the classic textbook examples), so we can be confident the algorithms are
implemented correctly. Run it with:

    python test_scheduler.py
"""

from scheduler import (
    Process, fcfs, sjf, srtf, round_robin,
    priority_scheduling, priority_preemptive, IDLE_LABEL,
)


def approx(a, b, tol=1e-9):
    return abs(a - b) < tol


def metrics_by_pid(result):
    return {m.pid: m for m in result.metrics}


def test_fcfs():
    procs = [
        Process("P1", arrival=0, burst=4),
        Process("P2", arrival=1, burst=3),
        Process("P3", arrival=2, burst=1),
    ]
    r = fcfs(procs)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion, m["P3"].completion) == (4, 7, 8)
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (0, 3, 5)
    assert approx(r.avg_waiting, 8 / 3)
    assert approx(r.avg_turnaround, 16 / 3)
    assert r.gantt == [("P1", 0, 4), ("P2", 4, 7), ("P3", 7, 8)]
    print("FCFS                  OK   avg wait = %.3f" % r.avg_waiting)


def test_fcfs_with_idle_gap():
    # The CPU should sit idle from t=0..2 before P1 arrives.
    procs = [Process("P1", arrival=2, burst=2), Process("P2", arrival=5, burst=2)]
    r = fcfs(procs)
    assert r.gantt[0] == (IDLE_LABEL, 0, 2)
    assert r.gantt[2] == (IDLE_LABEL, 4, 5)  # idle again until P2 arrives
    assert approx(r.cpu_utilization, 4 / 7 * 100)
    print("FCFS (idle handling)  OK   cpu util = %.1f%%" % r.cpu_utilization)


def test_sjf():
    procs = [
        Process("P1", arrival=0, burst=4),
        Process("P2", arrival=1, burst=3),
        Process("P3", arrival=2, burst=1),
    ]
    r = sjf(procs)
    m = metrics_by_pid(r)
    # At t=4 both P2 and P3 are ready; the shorter P3 runs first.
    assert r.gantt == [("P1", 0, 4), ("P3", 4, 5), ("P2", 5, 8)]
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (0, 4, 2)
    assert approx(r.avg_waiting, 2.0)
    print("SJF                   OK   avg wait = %.3f" % r.avg_waiting)


def test_srtf():
    # Classic Silberschatz example; the known answer is avg waiting = 6.5.
    procs = [
        Process("P1", arrival=0, burst=8),
        Process("P2", arrival=1, burst=4),
        Process("P3", arrival=2, burst=9),
        Process("P4", arrival=3, burst=5),
    ]
    r = srtf(procs)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion,
            m["P3"].completion, m["P4"].completion) == (17, 5, 26, 10)
    assert approx(r.avg_waiting, 6.5)
    assert approx(r.avg_turnaround, 13.0)
    print("SRTF                  OK   avg wait = %.3f" % r.avg_waiting)


def test_round_robin():
    # Classic example: three jobs all arriving at 0 with quantum 4.
    procs = [
        Process("P1", arrival=0, burst=24),
        Process("P2", arrival=0, burst=3),
        Process("P3", arrival=0, burst=3),
    ]
    r = round_robin(procs, quantum=4)
    m = metrics_by_pid(r)
    assert (m["P1"].completion, m["P2"].completion, m["P3"].completion) == (30, 7, 10)
    assert (m["P1"].waiting, m["P2"].waiting, m["P3"].waiting) == (6, 4, 7)
    assert approx(r.avg_waiting, 17 / 3)
    # Response time matters for RR: P3 waits for two slices before first run.
    assert m["P3"].response == 7
    print("Round Robin           OK   avg wait = %.3f" % r.avg_waiting)


def test_round_robin_with_arrivals():
    # Verifies the "new arrivals queue before the preempted process" rule.
    procs = [
        Process("P1", arrival=0, burst=5),
        Process("P2", arrival=1, burst=4),
        Process("P3", arrival=2, burst=2),
    ]
    r = round_robin(procs, quantum=2)
    # Expected order: P1[0-2] P2[2-4] P3[4-6] P1[6-8] P2[8-10] P1[10-11]
    assert r.gantt == [
        ("P1", 0, 2), ("P2", 2, 4), ("P3", 4, 6),
        ("P1", 6, 8), ("P2", 8, 10), ("P1", 10, 11),
    ]
    m = metrics_by_pid(r)
    assert m["P1"].completion == 11
    assert m["P2"].completion == 10
    assert m["P3"].completion == 6
    print("Round Robin (arrivals)OK   avg wait = %.3f" % r.avg_waiting)


def test_priority_non_preemptive():
    # Classic example, all arriving at 0; known avg waiting = 8.2.
    procs = [
        Process("P1", arrival=0, burst=10, priority=3),
        Process("P2", arrival=0, burst=1, priority=1),
        Process("P3", arrival=0, burst=2, priority=4),
        Process("P4", arrival=0, burst=1, priority=5),
        Process("P5", arrival=0, burst=5, priority=2),
    ]
    r = priority_scheduling(procs)
    assert r.execution_order == ["P2", "P5", "P1", "P3", "P4"]
    assert approx(r.avg_waiting, 8.2)
    assert approx(r.avg_turnaround, 12.0)
    print("Priority (non-preempt)OK   avg wait = %.3f" % r.avg_waiting)


def test_priority_preemptive():
    procs = [
        Process("P1", arrival=0, burst=4, priority=3),
        Process("P2", arrival=1, burst=3, priority=1),  # preempts P1 at t=1
        Process("P3", arrival=2, burst=1, priority=2),
    ]
    r = priority_preemptive(procs)
    # P1[0-1] P2[1-4] (highest prio) P3[4-5] P1[5-8]
    assert r.gantt == [("P1", 0, 1), ("P2", 1, 4), ("P3", 4, 5), ("P1", 5, 8)]
    m = metrics_by_pid(r)
    assert m["P1"].completion == 8 and m["P2"].completion == 4
    print("Priority (preemptive) OK   avg wait = %.3f" % r.avg_waiting)


def test_single_process():
    r = fcfs([Process("P1", arrival=3, burst=5)])
    m = metrics_by_pid(r)
    assert m["P1"].waiting == 0 and m["P1"].turnaround == 5
    assert m["P1"].completion == 8 and m["P1"].response == 0
    print("Single process        OK")


def test_validation():
    for bad in (
        lambda: Process("P1", arrival=-1, burst=2),
        lambda: Process("P1", arrival=0, burst=0),
    ):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for invalid process")

    try:
        fcfs([])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty process list")

    try:
        fcfs([Process("P1", 0, 2), Process("P1", 0, 3)])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for duplicate pids")
    print("Validation            OK")


def main():
    tests = [
        test_fcfs,
        test_fcfs_with_idle_gap,
        test_sjf,
        test_srtf,
        test_round_robin,
        test_round_robin_with_arrivals,
        test_priority_non_preemptive,
        test_priority_preemptive,
        test_single_process,
        test_validation,
    ]
    print("Running scheduling engine tests\n" + "-" * 40)
    for t in tests:
        t()
    print("-" * 40)
    print("All %d tests passed." % len(tests))


if __name__ == "__main__":
    main()
