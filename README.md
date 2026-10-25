# SeQUeNCe GUI

Topology editor with a standalone Python experiment runner, based on `sequence-toolbox/sequence-gui`.

With Python 3.12+ and uv installed, start from this repository with the upstream dependency lock:

```sh
uv run --frozen --no-install-project python -m sequence-gui.gui
```

Open http://127.0.0.1:8050/. Edit nodes/links, press **Submit**, then **Run**; the edited topology is passed automatically.
The Run panel accepts topology JSON, experiment-parameter JSON, and a standalone Python file. Parameters and Python are editable in the panel.
The included request experiment is a sample; your script owns protocol selection, topology construction, initialization, and execution.

The script receives `sys.argv[1] = topology.json` and `sys.argv[2] = simulation.json` and runs with the GUI's Python environment in a fresh `sequence-gui/runs/run-*` directory.
Its inputs, `experiment.py`, and `output.txt` remain there. stdout/stderr and the exit code appear after completion. **Export → All** downloads the three input files.
Replay from that directory with `python experiment.py topology.json simulation.json`. Additional modules/data must be installed or explicitly located by the script.

Existing GUI limits remain: use **Edit**, not View-table cell edits; classical links use **Latency** (twice the one-way delay, in ps; blank means no channel).
Multiplexing is unfinished, the default QKD template cannot be converted, and parallel directed channels / `cconnections` are unsupported. Run has no cancellation or live output.
