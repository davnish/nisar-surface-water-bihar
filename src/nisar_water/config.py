"""Experiment config schema. Every experiment is one YAML file validated here."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from nisar_water import REPO_ROOT


class DataCfg(BaseModel):
    band: Literal["L", "S"] = "L"
    granules: list[str] = Field(default_factory=list, description="GCOV .h5 filenames under data/raw/nisar_<band>")
    frequency: str = "frequencyA"
    terms: list[str] = Field(default_factory=lambda: ["HHHH", "HVHV"])
    extent: Literal["bbox", "full"] = "bbox"


class PreprocessCfg(BaseModel):
    speckle: dict[str, Any] = Field(default_factory=lambda: {"name": "none"})
    to_db: bool = True


class MethodCfg(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ValidationCfg(BaseModel):
    reference: str | None = None  # path to reference water raster (1 water, 0 land, 255 nodata)
    split: Literal["all", "train", "test"] = "test"


class ExperimentCfg(BaseModel):
    id: str
    question: str
    task: Literal["inventory", "reference", "separability", "water_mask", "change", "production"]
    data: DataCfg = Field(default_factory=DataCfg)
    preprocess: PreprocessCfg = Field(default_factory=PreprocessCfg)
    method: MethodCfg | None = None
    validation: ValidationCfg = Field(default_factory=ValidationCfg)
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def exp_dir(self) -> Path:
        return REPO_ROOT / "experiments" / self.id


def load_config(path: str | Path) -> ExperimentCfg:
    with open(path) as f:
        return ExperimentCfg.model_validate(yaml.safe_load(f))


def load_aoi() -> dict:
    with open(REPO_ROOT / "configs" / "aoi.yaml") as f:
        return yaml.safe_load(f)


def load_paths() -> dict[str, Path]:
    with open(REPO_ROOT / "configs" / "paths.yaml") as f:
        return {k: REPO_ROOT / v for k, v in yaml.safe_load(f).items()}
