"""ExperimentConfig — A/B experiment configuration model and loader.

Each experiment defines an experiment_id, two variants (A/B), shared parameters,
and a metric_keys list specifying which numeric outcomes drive the comparison.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class VariantConfig(BaseModel):
    variant: str = Field(description="Variant label, typically 'A' or 'B'.")
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class ExperimentConfig(BaseModel):
    experiment_id: str
    description: str = ""
    metric_keys: list[str] = Field(default_factory=list)
    higher_is_better: list[str] = Field(default_factory=list)
    variants: list[VariantConfig] = Field(default_factory=list)
    dataset: str | None = None

    def variant(self, name: str) -> VariantConfig:
        for v in self.variants:
            if v.variant == name:
                return v
        raise KeyError(
            f"Variant '{name}' not found in experiment '{self.experiment_id}'"
        )

    def variant_names(self) -> list[str]:
        return [v.variant for v in self.variants]


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix in {".json"}:
        data = json.loads(raw)
    else:
        # Allow yaml-like syntax via json fallback (we don't ship pyyaml as core dep)
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(raw)
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML required to parse non-JSON experiment configs"
            ) from exc
    return ExperimentConfig.model_validate(data)
