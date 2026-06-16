#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze HyDE experiment results and compute p-values."""
import sys
import os
import json
from pathlib import Path

if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))


def main():
    # Load report
    report_path = Path("app/experiments/reports/hyde_comparison_report.json")
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    variants = report['variants']
    if len(variants) != 2:
        print("Error: Expected 2 variants")
        return 1

    a = variants[0]
    b = variants[1]

    print("=" * 80)
    print("HyDE A/B Experiment Results")
    print("=" * 80)
    print()
    print(f"Dataset: 168 samples (146 valid after filtering paper_20260509_004)")
    print(f"Variants: A (Vector baseline) vs B (HyDE)")
    print()

    # Print metrics
    print("Raw Metrics:")
    print("-" * 80)
    print(f"{'Metric':<20s} {'A: Vector':<15s} {'B: HyDE':<15s} {'Delta':<15s} {'% Change':<15s}")
    print("-" * 80)

    metrics_to_compare = ['hit_at_5', 'mrr', 'retrieval_time']

    for metric in metrics_to_compare:
        val_a = a['metrics'][metric]
        val_b = b['metrics'][metric]
        delta = val_b - val_a
        pct = (delta / val_a * 100) if val_a != 0 else 0

        print(f"{metric:<20s} {val_a:<15.4f} {val_b:<15.4f} {delta:<+15.4f} {pct:<+15.2f}%")

    # Compute p-values using t-test
    print()
    print("Statistical Significance (Welch t-test):")
    print("-" * 80)

    from scipy import stats

    for metric in metrics_to_compare:
        samples_a = a['samples'][metric]
        samples_b = b['samples'][metric]

        if len(samples_a) > 1 and len(samples_b) > 1:
            t_stat, p_value = stats.ttest_ind(samples_a, samples_b, equal_var=False)
            is_sig = p_value < 0.05
            sig_marker = "✅ Significant" if is_sig else "❌ Not significant"

            print(f"\n{metric}:")
            print(f"  t-statistic = {t_stat:.4f}")
            print(f"  p-value     = {p_value:.6f}")
            print(f"  α = 0.05    : {sig_marker}")

    # Summary
    print()
    print("=" * 80)
    print("Summary and Recommendation:")
    print("-" * 80)

    hit_a = a['metrics']['hit_at_5']
    hit_b = b['metrics']['hit_at_5']
    samples_a = a['samples']['hit_at_5']
    samples_b = b['samples']['hit_at_5']
    t_stat, p_value = stats.ttest_ind(samples_a, samples_b, equal_var=False)

    hit_delta_pct = (hit_b - hit_a) / hit_a * 100
    time_a = a['metrics']['retrieval_time']
    time_b = b['metrics']['retrieval_time']
    time_increase = (time_b - time_a) / time_a * 100

    print()
    if p_value < 0.05:
        if hit_b > hit_a:
            print(f"✅ HyDE shows statistically SIGNIFICANT IMPROVEMENT")
            print(f"   - hit@5: +{hit_delta_pct:.1f}% improvement (p={p_value:.4f} < 0.05)")
            print(f"   - Cost: +{time_increase:.1f}% latency ({time_b:.2f}s vs {time_a:.2f}s)")
            print()
            print("   Recommendation: ADOPT HyDE")
            print("   Reason: Significant recall improvement justifies latency cost for QA tasks")
        else:
            print(f"⚠️  HyDE shows statistically SIGNIFICANT DEGRADATION")
            print(f"   - hit@5: {hit_delta_pct:.1f}% decline (p={p_value:.4f} < 0.05)")
            print()
            print("   Recommendation: DO NOT ADOPT HyDE")
            print("   Reason: Significant quality decline")
    else:
        print(f"❌ HyDE does NOT show statistically significant improvement")
        print(f"   - hit@5: {hit_delta_pct:+.1f}% change (p={p_value:.4f} > 0.05)")
        print(f"   - p-value > 0.05 means the difference could be random variation")
        print()
        print("   Recommendation: DO NOT ADOPT HyDE")
        print("   Reason: No proven benefit, adds latency cost (+{:.1f}%)".format(time_increase))

    print()
    print("=" * 80)

    # Update report file with complete analysis
    report['deltas'] = {
        metric: {
            "variant_a": a['metrics'][metric],
            "variant_b": b['metrics'][metric],
            "delta": b['metrics'][metric] - a['metrics'][metric],
            "relative_change": (b['metrics'][metric] - a['metrics'][metric]) / a['metrics'][metric] if a['metrics'][metric] != 0 else 0
        }
        for metric in metrics_to_compare
    }

    report['significance'] = {}
    for metric in metrics_to_compare:
        samples_a = a['samples'][metric]
        samples_b = b['samples'][metric]
        if len(samples_a) > 1 and len(samples_b) > 1:
            t_stat, p_value = stats.ttest_ind(samples_a, samples_b, equal_var=False)
            report['significance'][metric] = {
                "test": "welch_t",
                "t_stat": float(t_stat),
                "p_value": float(p_value),
                "significant_at_0.05": bool(p_value < 0.05)
            }

    # Determine winner
    if report['significance']['hit_at_5']['significant_at_0.05']:
        report['winner'] = 'B' if hit_b > hit_a else 'A'
    else:
        report['winner'] = 'A'  # Baseline wins if no significant improvement

    # Save updated report
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Updated report saved to:", report_path)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
