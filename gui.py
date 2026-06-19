"""
gui.py - Tkinter graphical interface for the CPU scheduling simulator.

The window is split into two halves:

* Left  - an editable table of processes plus the controls used to add, edit,
          remove, randomise and run them.
* Right - a tabbed results area with three tabs: the Gantt chart and
          per-process metrics for a single algorithm, an automatic statistical
          comparison of every algorithm, and all six Gantt charts stacked on a
          shared time axis for visual comparison.

All of the actual scheduling is done by scheduler.py; this file is only
concerned with presenting the inputs and results.
"""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
matplotlib.use("TkAgg")  # render Matplotlib figures inside Tkinter
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import scheduler
from scheduler import Process, IDLE_LABEL


# Shorter labels so the comparison chart's x-axis stays readable.
SHORT_NAMES = {
    "FCFS": "FCFS",
    "SJF (Non-preemptive)": "SJF",
    "SRTF (Preemptive SJF)": "SRTF",
    "Round Robin": "RR",
    "Priority (Non-preemptive)": "Priority",
    "Priority (Preemptive)": "Priority-P",
}


class SchedulerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CPU Scheduling Simulator")
        self.geometry("1200x740")
        self.minsize(1040, 660)

        # ``self.processes`` is the single source of truth; the table on screen
        # is always rebuilt from it.
        self.processes: list[Process] = []
        self.current_result: scheduler.ScheduleResult | None = None
        self.comparison_results: list[scheduler.ScheduleResult] | None = None
        self._color_cache: dict[str, object] = {}
        self._cmap = matplotlib.colormaps["tab20"]

        self._build_controls()
        self._build_results()

        self._load_sample_workload()

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_controls(self):
        """Build the left-hand input/control panel."""
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Processes", font=("Segoe UI", 12, "bold")).pack(
            anchor="w")

        # --- process table -------------------------------------------------
        cols = ("pid", "arrival", "burst", "priority")
        headings = ("Process", "Arrival", "Burst", "Priority")
        table_frame = ttk.Frame(left)
        table_frame.pack(fill="x", pady=(4, 6))
        self.proc_tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", height=8,
            selectmode="browse")
        for c, h in zip(cols, headings):
            self.proc_tree.heading(c, text=h)
            self.proc_tree.column(c, width=92, anchor="center")
        self.proc_tree.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(table_frame, orient="vertical",
                           command=self.proc_tree.yview)
        sb.pack(side="right", fill="y")
        self.proc_tree.configure(yscrollcommand=sb.set)
        self.proc_tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        # --- entry fields --------------------------------------------------
        form = ttk.LabelFrame(left, text="Add / edit process", padding=8)
        form.pack(fill="x", pady=4)
        self.var_pid = tk.StringVar()
        self.var_arrival = tk.StringVar()
        self.var_burst = tk.StringVar()
        self.var_priority = tk.StringVar(value="1")
        fields = [
            ("Process ID", self.var_pid),
            ("Arrival Time", self.var_arrival),
            ("Burst Time", self.var_burst),
            ("Priority", self.var_priority),
        ]
        for row, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w",
                                             padx=2, pady=2)
            ttk.Entry(form, textvariable=var, width=14).grid(
                row=row, column=1, padx=2, pady=2)
        ttk.Label(form, text="(smaller priority = higher)",
                  foreground="#666").grid(row=4, column=0, columnspan=2,
                                          sticky="w", pady=(2, 0))

        btns = ttk.Frame(form)
        btns.grid(row=5, column=0, columnspan=2, pady=(6, 0), sticky="we")
        ttk.Button(btns, text="Add", command=self._add_process).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(btns, text="Update", command=self._update_process).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(btns, text="Remove", command=self._remove_process).pack(
            side="left", expand=True, fill="x", padx=1)

        # --- workload buttons ---------------------------------------------
        wl = ttk.Frame(left)
        wl.pack(fill="x", pady=(2, 8))
        ttk.Button(wl, text="Random Workload",
                   command=self._random_workload).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(wl, text="Clear All", command=self._clear_all).pack(
            side="left", expand=True, fill="x", padx=1)

        # --- algorithm selection ------------------------------------------
        algo = ttk.LabelFrame(left, text="Algorithm", padding=8)
        algo.pack(fill="x", pady=4)
        self.var_algo = tk.StringVar(value="FCFS")
        self.algo_combo = ttk.Combobox(
            algo, textvariable=self.var_algo, state="readonly",
            values=list(scheduler.ALGORITHMS.keys()))
        self.algo_combo.pack(fill="x")
        self.algo_combo.bind("<<ComboboxSelected>>", self._on_algo_changed)

        q_row = ttk.Frame(algo)
        q_row.pack(fill="x", pady=(6, 0))
        ttk.Label(q_row, text="Time Quantum (Round Robin):").pack(side="left")
        self.var_quantum = tk.StringVar(value="2")
        self.quantum_entry = ttk.Spinbox(
            q_row, from_=1, to=100, width=5, textvariable=self.var_quantum)
        self.quantum_entry.pack(side="right")
        self._on_algo_changed()  # set initial enabled/disabled state

        # --- run / compare / export ---------------------------------------
        run = ttk.Frame(left)
        run.pack(fill="x", pady=(8, 2))
        ttk.Button(run, text="Run Selected Algorithm",
                   command=self._run_selected).pack(fill="x", pady=1)
        ttk.Button(run, text="Run All Algorithms",
                   command=self._compare_all).pack(fill="x", pady=1)

        export = ttk.Frame(left)
        export.pack(fill="x", pady=(8, 0))
        ttk.Button(export, text="Export Results (CSV)",
                   command=self._export_results).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(export, text="Save Chart (PNG)",
                   command=self._save_chart).pack(
            side="left", expand=True, fill="x", padx=1)

    def _build_results(self):
        """Build the right-hand tabbed results area."""
        right = ttk.Frame(self, padding=(4, 10, 10, 10))
        right.pack(side="left", fill="both", expand=True)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        # ----- Tab 1: Gantt chart + per-process metrics -------------------
        tab1 = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab1, text="Schedule & Metrics")

        self.gantt_fig = Figure(figsize=(7, 2.4), dpi=100)
        self.gantt_canvas = FigureCanvasTkAgg(self.gantt_fig, master=tab1)
        self.gantt_canvas.get_tk_widget().pack(fill="x")

        self.summary_var = tk.StringVar(value="Run a schedule to see results.")
        ttk.Label(tab1, textvariable=self.summary_var,
                  font=("Consolas", 9), foreground="#003366",
                  justify="left").pack(anchor="w", pady=(6, 4))

        metric_cols = ("pid", "arrival", "burst", "priority", "start",
                       "completion", "waiting", "turnaround", "response")
        metric_head = ("Process", "Arrival", "Burst", "Priority", "Start",
                       "Completion", "Waiting", "Turnaround", "Response")
        mframe = ttk.Frame(tab1)
        mframe.pack(fill="both", expand=True)
        self.metric_tree = ttk.Treeview(
            mframe, columns=metric_cols, show="headings")
        for c, h in zip(metric_cols, metric_head):
            self.metric_tree.heading(c, text=h)
            self.metric_tree.column(c, width=84, anchor="center")
        self.metric_tree.pack(side="left", fill="both", expand=True)
        msb = ttk.Scrollbar(mframe, orient="vertical",
                            command=self.metric_tree.yview)
        msb.pack(side="right", fill="y")
        self.metric_tree.configure(yscrollcommand=msb.set)

        # ----- Tab 2: comparison ------------------------------------------
        tab2 = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab2, text="Comparison")

        self.cmp_fig = Figure(figsize=(7, 3.0), dpi=100)
        self.cmp_canvas = FigureCanvasTkAgg(self.cmp_fig, master=tab2)
        self.cmp_canvas.get_tk_widget().pack(fill="both", expand=True)

        cmp_cols = ("algo", "waiting", "turnaround", "response", "util",
                    "throughput")
        cmp_head = ("Algorithm", "Avg Waiting", "Avg Turnaround",
                    "Avg Response", "CPU Util %", "Throughput")
        cframe = ttk.Frame(tab2)
        cframe.pack(fill="x", pady=(6, 0))
        self.cmp_tree = ttk.Treeview(
            cframe, columns=cmp_cols, show="headings", height=7)
        widths = (170, 100, 110, 100, 90, 90)
        for c, h, w in zip(cmp_cols, cmp_head, widths):
            self.cmp_tree.heading(c, text=h)
            self.cmp_tree.column(c, width=w, anchor="center")
        self.cmp_tree.column("algo", anchor="w")
        self.cmp_tree.pack(fill="x")
        # Highlight the best (lowest average waiting) algorithm in green.
        self.cmp_tree.tag_configure("best", background="#d7f5d7")
        ttk.Label(tab2, text="Green row = lowest average waiting time.",
                  foreground="#666").pack(anchor="w", pady=(4, 0))

        # ----- Tab 3: all Gantt charts stacked together -------------------
        tab3 = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab3, text="All Gantt Charts")

        self.all_fig = Figure(figsize=(7, 6.2), dpi=100)
        self.all_canvas = FigureCanvasTkAgg(self.all_fig, master=tab3)
        self.all_canvas.get_tk_widget().pack(fill="both", expand=True)

        self._draw_gantt(None)
        self._draw_comparison(None)
        self._draw_all_gantts(None)

    # ------------------------------------------------------------------
    # Process table management
    # ------------------------------------------------------------------
    def _refresh_process_table(self):
        self.proc_tree.delete(*self.proc_tree.get_children())
        for p in self.processes:
            self.proc_tree.insert("", "end", iid=p.pid,
                                  values=(p.pid, p.arrival, p.burst, p.priority))

    def _suggest_pid(self) -> str:
        """Suggest the next free "P<n>" id."""
        n = 1
        existing = {p.pid for p in self.processes}
        while f"P{n}" in existing:
            n += 1
        return f"P{n}"

    def _read_form(self):
        """Validate and return (pid, arrival, burst, priority) from the form."""
        pid = self.var_pid.get().strip()
        if not pid:
            raise ValueError("Process ID cannot be empty.")
        try:
            arrival = int(self.var_arrival.get())
            burst = int(self.var_burst.get())
            priority = int(self.var_priority.get())
        except ValueError:
            raise ValueError("Arrival, Burst and Priority must be integers.")
        # Reuse the model's own validation (arrival >= 0, burst > 0).
        Process(pid, arrival, burst, priority)
        return pid, arrival, burst, priority

    def _add_process(self):
        try:
            pid, arrival, burst, priority = self._read_form()
            if any(p.pid == pid for p in self.processes):
                raise ValueError(f"A process with id '{pid}' already exists.")
            self.processes.append(Process(pid, arrival, burst, priority))
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._refresh_process_table()
        self._clear_form()

    def _update_process(self):
        sel = self.proc_tree.selection()
        if not sel:
            messagebox.showinfo("Update", "Select a process in the table first.")
            return
        old_pid = sel[0]
        try:
            pid, arrival, burst, priority = self._read_form()
            if pid != old_pid and any(p.pid == pid for p in self.processes):
                raise ValueError(f"A process with id '{pid}' already exists.")
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        for i, p in enumerate(self.processes):
            if p.pid == old_pid:
                self.processes[i] = Process(pid, arrival, burst, priority)
                break
        self._refresh_process_table()
        self._clear_form()

    def _remove_process(self):
        sel = self.proc_tree.selection()
        if not sel:
            messagebox.showinfo("Remove", "Select a process in the table first.")
            return
        pid = sel[0]
        self.processes = [p for p in self.processes if p.pid != pid]
        self._refresh_process_table()
        self._clear_form()

    def _clear_all(self):
        if self.processes and messagebox.askyesno(
                "Clear all", "Remove every process?"):
            self.processes.clear()
            self._refresh_process_table()
            self._clear_form()

    def _random_workload(self):
        self.processes = scheduler.generate_random_workload(count=5)
        self._refresh_process_table()
        self._clear_form()

    def _clear_form(self):
        self.var_pid.set(self._suggest_pid())
        self.var_arrival.set("0")
        self.var_burst.set("")
        self.var_priority.set("1")

    def _on_row_selected(self, _event=None):
        sel = self.proc_tree.selection()
        if not sel:
            return
        for p in self.processes:
            if p.pid == sel[0]:
                self.var_pid.set(p.pid)
                self.var_arrival.set(str(p.arrival))
                self.var_burst.set(str(p.burst))
                self.var_priority.set(str(p.priority))
                break

    def _on_algo_changed(self, _event=None):
        is_rr = self.var_algo.get() == "Round Robin"
        self.quantum_entry.configure(state="normal" if is_rr else "disabled")

    # ------------------------------------------------------------------
    # Running the algorithms
    # ------------------------------------------------------------------
    def _quantum(self) -> int:
        try:
            q = int(self.var_quantum.get())
        except ValueError:
            q = 2
        return max(1, q)

    def _run_selected(self):
        if not self.processes:
            messagebox.showinfo("Run", "Add at least one process first.")
            return
        try:
            result = scheduler.run_algorithm(
                self.var_algo.get(), self.processes, self._quantum())
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.current_result = result
        self._draw_gantt(result)
        self._fill_metrics(result)
        self.notebook.select(0)

    def _compare_all(self):
        if not self.processes:
            messagebox.showinfo("Run All", "Add at least one process first.")
            return
        results = scheduler.compare_all(self.processes, self._quantum())
        self.comparison_results = results
        self._draw_comparison(results)
        self._fill_comparison_table(results)
        self._draw_all_gantts(results)
        self.notebook.select(2)  # show the stacked Gantt charts (the new view)

    # ------------------------------------------------------------------
    # Drawing / displaying results
    # ------------------------------------------------------------------
    def _color_for(self, label):
        if label == IDLE_LABEL:
            return "#e6e6e6"
        if label not in self._color_cache:
            idx = len(self._color_cache) % self._cmap.N
            self._color_cache[label] = self._cmap(idx)
        return self._color_cache[label]

    def _draw_gantt(self, result):
        self.gantt_fig.clear()
        ax = self.gantt_fig.add_subplot(111)

        if result is None or not result.gantt:
            ax.text(0.5, 0.5, "Run a schedule to see the Gantt chart",
                    ha="center", va="center", fontsize=11, color="#888")
            ax.axis("off")
            self.gantt_canvas.draw()
            return

        for label, start, end in result.gantt:
            is_idle = label == IDLE_LABEL
            ax.barh(0, end - start, left=start, height=0.6,
                    color=self._color_for(label),
                    edgecolor="black", linewidth=0.8,
                    hatch="//" if is_idle else None)
            ax.text((start + end) / 2, 0, label, ha="center", va="center",
                    fontsize=8, color="#333" if is_idle else "black")

        boundaries = sorted({b for _, s, e in result.gantt for b in (s, e)})
        ax.set_xticks(boundaries)
        ax.set_yticks([])
        ax.set_ylim(-0.5, 0.5)
        ax.set_xlabel("Time")
        title = f"Gantt Chart — {result.algorithm}"
        if result.quantum is not None:
            title += f" (quantum = {result.quantum})"
        ax.set_title(title, fontsize=10)
        self.gantt_fig.tight_layout()
        self.gantt_canvas.draw()

    def _fill_metrics(self, result):
        self.metric_tree.delete(*self.metric_tree.get_children())
        for m in result.metrics:
            self.metric_tree.insert(
                "", "end",
                values=(m.pid, m.arrival, m.burst, m.priority, m.start,
                        m.completion, m.waiting, m.turnaround, m.response))
        order = " → ".join(result.execution_order)
        self.summary_var.set(
            f"Execution order : {order}\n"
            f"Avg Waiting Time    = {result.avg_waiting:.2f}      "
            f"Avg Turnaround Time = {result.avg_turnaround:.2f}\n"
            f"Avg Response Time   = {result.avg_response:.2f}      "
            f"CPU Utilization = {result.cpu_utilization:.1f}%      "
            f"Throughput = {result.throughput:.3f}")

    def _draw_comparison(self, results):
        self.cmp_fig.clear()
        ax = self.cmp_fig.add_subplot(111)

        if not results:
            ax.text(0.5, 0.5, "Click 'Compare All Algorithms'",
                    ha="center", va="center", fontsize=11, color="#888")
            ax.axis("off")
            self.cmp_canvas.draw()
            return

        names = [SHORT_NAMES.get(r.algorithm, r.algorithm) for r in results]
        waiting = [r.avg_waiting for r in results]
        turnaround = [r.avg_turnaround for r in results]
        response = [r.avg_response for r in results]
        x = range(len(names))
        w = 0.27
        ax.bar([i - w for i in x], waiting, w, label="Avg Waiting")
        ax.bar(list(x), turnaround, w, label="Avg Turnaround")
        ax.bar([i + w for i in x], response, w, label="Avg Response")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, fontsize=8)
        ax.set_ylabel("Time units")
        ax.set_title("Average Times by Algorithm", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle=":", alpha=0.5)
        self.cmp_fig.tight_layout()
        self.cmp_canvas.draw()

    def _fill_comparison_table(self, results):
        self.cmp_tree.delete(*self.cmp_tree.get_children())
        best = min(results, key=lambda r: r.avg_waiting)
        for r in results:
            tag = ("best",) if r is best else ()
            self.cmp_tree.insert(
                "", "end", tags=tag,
                values=(r.algorithm, f"{r.avg_waiting:.2f}",
                        f"{r.avg_turnaround:.2f}", f"{r.avg_response:.2f}",
                        f"{r.cpu_utilization:.1f}", f"{r.throughput:.3f}"))

    def _draw_all_gantts(self, results):
        """Stack every algorithm's Gantt chart on one shared time axis.

        Each algorithm gets its own row, all rows share the same x-axis so the
        schedules line up for visual comparison, and a process keeps the same
        colour across every row (handled by ``_color_for``).
        """
        self.all_fig.clear()

        if not results:
            ax = self.all_fig.add_subplot(111)
            ax.text(0.5, 0.5, "Click 'Run All Algorithms' to see every schedule",
                    ha="center", va="center", fontsize=11, color="#888")
            ax.axis("off")
            self.all_canvas.draw()
            return

        max_time = max((r.gantt[-1][2] for r in results if r.gantt), default=1)
        rows = self.all_fig.subplots(len(results), 1, sharex=True,
                                     squeeze=False)
        axes = [row[0] for row in rows]

        for ax, result in zip(axes, results):
            for label, start, end in result.gantt:
                is_idle = label == IDLE_LABEL
                ax.barh(0, end - start, left=start, height=0.6,
                        color=self._color_for(label), edgecolor="black",
                        linewidth=0.6, hatch="//" if is_idle else None)
                ax.text((start + end) / 2, 0, label, ha="center", va="center",
                        fontsize=7, color="#333" if is_idle else "black")
            ax.set_yticks([])
            ax.set_ylim(-0.5, 0.5)
            ax.set_xlim(0, max_time)
            ax.set_ylabel(
                f"{SHORT_NAMES.get(result.algorithm, result.algorithm)}\n"
                f"wait {result.avg_waiting:.1f}",
                rotation=0, ha="right", va="center", fontsize=8)
            ax.grid(axis="x", linestyle=":", alpha=0.4)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.label_outer()  # only the bottom row shows the time tick labels

        axes[-1].set_xlabel("Time")
        self.all_fig.suptitle("Gantt Charts — All Algorithms", fontsize=11)
        self.all_fig.tight_layout(rect=(0, 0, 1, 0.97))
        self.all_canvas.draw()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_results(self):
        if not self.current_result:
            messagebox.showinfo("Export", "Run an algorithm first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{SHORT_NAMES.get(self.current_result.algorithm, 'result')}_results.csv")
        if not path:
            return
        r = self.current_result
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([f"Algorithm: {r.algorithm}"])
                if r.quantum is not None:
                    writer.writerow([f"Time quantum: {r.quantum}"])
                writer.writerow([])
                writer.writerow(["Process", "Arrival", "Burst", "Priority",
                                 "Start", "Completion", "Waiting",
                                 "Turnaround", "Response"])
                for m in r.metrics:
                    writer.writerow([m.pid, m.arrival, m.burst, m.priority,
                                     m.start, m.completion, m.waiting,
                                     m.turnaround, m.response])
                writer.writerow([])
                writer.writerow(["Average Waiting Time", f"{r.avg_waiting:.4f}"])
                writer.writerow(["Average Turnaround Time",
                                 f"{r.avg_turnaround:.4f}"])
                writer.writerow(["Average Response Time",
                                 f"{r.avg_response:.4f}"])
                writer.writerow(["CPU Utilization (%)",
                                 f"{r.cpu_utilization:.2f}"])
                writer.writerow(["Throughput", f"{r.throughput:.4f}"])
                writer.writerow(["Execution Order",
                                 " -> ".join(r.execution_order)])
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Export", f"Results saved to:\n{path}")

    def _save_chart(self):
        # Save whichever tab is currently in front.
        fig, name = {
            0: (self.gantt_fig, "gantt_chart.png"),
            1: (self.cmp_fig, "comparison_chart.png"),
            2: (self.all_fig, "all_gantt_charts.png"),
        }[self.notebook.index(self.notebook.select())]
        path = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile=name,
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")])
        if not path:
            return
        try:
            fig.savefig(path, dpi=150, bbox_inches="tight")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        messagebox.showinfo("Save chart", f"Chart saved to:\n{path}")

    # ------------------------------------------------------------------
    def _load_sample_workload(self):
        """Start with a small workload so the window is not empty."""
        self.processes = [
            Process("P1", 0, 5, 2),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 8, 4),
            Process("P4", 3, 6, 3),
        ]
        self._refresh_process_table()
        self._clear_form()


def launch():
    app = SchedulerApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
