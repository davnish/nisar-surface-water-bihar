"""Experiment runner: one config -> one timestamped run folder with provenance, metrics and figures."""
from __future__ import annotations

import importlib
import json
import logging
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from nisar_water import provenance
from nisar_water.config import ExperimentCfg, load_config


@dataclass
class RunContext:
    cfg: ExperimentCfg
    run_dir: Path
    log: logging.Logger
    metrics: dict = field(default_factory=dict)
    inputs: list[Path] = field(default_factory=list)

    @property
    def figures(self) -> Path:
        return self.run_dir / "figures"

    @property
    def outputs(self) -> Path:
        return self.run_dir / "outputs"


def _task(name: str):
    """Task `name` is the `run(ctx)` function in nisar_water/tasks/<name>.py."""
    try:
        module = importlib.import_module(f"nisar_water.tasks.{name}")
    except ModuleNotFoundError as e:
        if e.name == f"nisar_water.tasks.{name}":
            raise NotImplementedError(f"task {name!r} not implemented yet (no nisar_water/tasks/{name}.py)") from e
        raise
    return module.run


def run_experiment(config_path: str | Path) -> Path:
    cfg = load_config(config_path)
    run_dir = cfg.exp_dir / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    for sub in ("figures", "outputs"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy(config_path, run_dir / "config.yaml")

    log = logging.getLogger(cfg.id)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in (logging.FileHandler(run_dir / "log.txt"), logging.StreamHandler()):
        h.setFormatter(fmt)
        log.addHandler(h)

    ctx = RunContext(cfg=cfg, run_dir=run_dir, log=log)
    log.info("running %s (%s) -> %s", cfg.id, cfg.task, run_dir)
    try:
        _task(cfg.task)(ctx)
    except Exception:
        # keep the folder (log + config) for debugging; report/index skip runs without metrics.json
        (run_dir / "FAILED").write_text(traceback.format_exc())
        log.exception("run failed")
        raise

    (run_dir / "provenance.json").write_text(json.dumps(provenance.collect(ctx.inputs), indent=2))
    (run_dir / "metrics.json").write_text(json.dumps(ctx.metrics, indent=2, default=str))
    from nisar_water.report import write_run_results
    write_run_results(run_dir, ctx.metrics)
    log.info("done: %s", run_dir)
    return run_dir
