#!/usr/bin/env python
"""Run HyDE A/B experiment and generate report.

Usage:
    python run_hyde_experiment.py

This will:
1. Run hyde_comparison experiment (168 samples, vector vs HyDE)
2. Generate JSON and Markdown reports in app/experiments/reports/
3. Print summary statistics and p-values
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.experiments.runner import run_full_experiment, load_experiment_config


def main():
    print("=" * 80)
    print("HyDE A/B Experiment Runner")
    print("=" * 80)
    print()
    print("Experiment: hyde_comparison")
    print("Dataset: 168 QA samples across 9 papers")
    print("Variants:")
    print("  A: Vector-only (baseline)")
    print("  B: HyDE (generate hypothetical document, then embed)")
    print()
    print("Running experiment... (this may take 5-10 minutes due to LLM calls)")
    print()

    scenario_path = Path("app/experiments/scenarios/hyde_comparison.json")
    if not scenario_path.exists():
        print(f"❌ Error: Scenario file not found: {scenario_path}")
        return 1

    config = load_experiment_config(scenario_path)

    try:
        report = run_full_experiment(
            config,
            output_dir=Path("app/experiments/reports"),
            executor="real"
        )
    except Exception as e:
        print(f"❌ Experiment failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    print("=" * 80)
    print("Experiment Complete!")
    print("=" * 80)
    print()
    print(f"Reports generated:")
    print(f"  - app/experiments/reports/hyde_comparison_report.json")
    print(f"  - app/experiments/reports/hyde_comparison_report.md")
    print()
    print("Summary:")
    print("-" * 80)

    # Print metrics
    for variant_result in report.variant_results:
        print(f"\n{variant_result.variant}:")
        for metric, value in variant_result.metrics.items():
            print(f"  {metric:20s} = {value:.4f}")

    # Print deltas and significance
    print("\nDeltas (B vs A):")
    print("-" * 80)
    for metric, delta_info in report.deltas.items():
        rel_change = delta_info["relative_change"] * 100
        print(f"\n{metric}:")
        print(f"  Δ absolute = {delta_info['delta']:+.4f}")
        print(f"  Δ relative = {rel_change:+.2f}%")

        sig = report.significance.get(metric, )
        if sig.get("test") == "welch_t":
            p_value = sig.get("p_value", 1.0)
            is_sig = sig.get("significant_at_0.05", False)
            sig_marker = "✅" if is_sig else "❌"
            print(f"  p-value = {p_value:.4f} {sig_marker}")
            print(f"  Significant at α=0.05: {is_sig}")

    print()
    print(f"Overall winner: {report.winner}")
    print()
    print("=" * 80)
    print("Recommendation:")
    print("-" * 80)

    # Decision logic
    hit_sig = report.significance.get("hit_at_5", {})
    if hit_sig.get("significant_at_0.05"):
        hit_delta = report.deltas.get("hit_at_5", ).get("relative_change", 0) * 100
        if hit_delta > 0:
            print("✅ HyDE shows statistically significant improvement in recall.")
            print(f"   Recommend adopting HyDE (hit@5 improvement: +{hit_delta:.1f}%, p<0.05)")
        else:
            print("⚠️  HyDE shows statistically significant degradation in recall.")
            print(f"   Recommend NOT adopting HyDE (hit@5 change: {hit_delta:.1f}%, p<0.05)")
    else:
        print("❌ HyDE does not show statistically significant improvement.")
        print("   p-value > 0.05, effect may be due to random variation.")
        print("   Recommend NOT adopting HyDE (stick with vector baseline)")

    print()
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
