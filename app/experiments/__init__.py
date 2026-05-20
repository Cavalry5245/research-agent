"""Experiments module: A/B testing framework for prompts, embeddings, and chunking strategies."""

from app.experiments.config import ExperimentConfig, VariantConfig, load_experiment_config

__all__ = [
    "ExperimentConfig",
    "VariantConfig",
    "load_experiment_config",
]


def __getattr__(name: str):  # lazy load to avoid runpy double-import warning
    if name in {"ExperimentRunner", "compare_variants", "generate_report", "run_full_experiment"}:
        from app.experiments import runner

        return getattr(runner, name)
    raise AttributeError(f"module 'app.experiments' has no attribute {name!r}")

