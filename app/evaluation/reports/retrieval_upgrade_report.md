# Retrieval Upgrade Report

## Overview
- Sample count: 11
- Top-k: 3
- Baseline strategy: dense
- Best strategy: dense_rerank
- Strategy count: 4

## Strategy Metrics
### dense
- Samples: 11
- Hit rate: 1.000
- Mean recall: 1.000
- MRR: 0.500
### dense_rerank
- Samples: 11
- Hit rate: 1.000
- Mean recall: 1.000
- MRR: 1.000
### hybrid
- Samples: 11
- Hit rate: 1.000
- Mean recall: 1.000
- MRR: 1.000
### hybrid_rerank
- Samples: 11
- Hit rate: 1.000
- Mean recall: 1.000
- MRR: 1.000

## Improvements vs Dense Baseline
### dense_rerank
- Δ Hit rate vs dense: +0.000
- Δ Mean recall vs dense: +0.000
- Δ MRR vs dense: +0.500
### hybrid
- Δ Hit rate vs dense: +0.000
- Δ Mean recall vs dense: +0.000
- Δ MRR vs dense: +0.500
### hybrid_rerank
- Δ Hit rate vs dense: +0.000
- Δ Mean recall vs dense: +0.000
- Δ MRR vs dense: +0.500

## Failure Case Samples
### dense
- Sample: paper_20260509_004-abstract
  - Query: What does the paper 'Receptive-Field and Direction Induced Attention' mainly propose or study?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-1
  - Query: According to the 'results' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-2
  - Query: According to the 'INTRODUCTION' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
### dense_rerank
- Sample: paper_20260509_004-abstract
  - Query: What does the paper 'Receptive-Field and Direction Induced Attention' mainly propose or study?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-1
  - Query: According to the 'results' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-2
  - Query: According to the 'INTRODUCTION' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
### hybrid
- Sample: paper_20260509_004-abstract
  - Query: What does the paper 'Receptive-Field and Direction Induced Attention' mainly propose or study?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-1
  - Query: According to the 'results' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-2
  - Query: According to the 'INTRODUCTION' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
### hybrid_rerank
- Sample: paper_20260509_004-abstract
  - Query: What does the paper 'Receptive-Field and Direction Induced Attention' mainly propose or study?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-1
  - Query: According to the 'results' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.
- Sample: paper_20260509_004-section-2
  - Query: According to the 'INTRODUCTION' section of 'Receptive-Field and Direction Induced Attention', what key information is highlighted?
  - Hit@k: True
  - Failure note: No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.

## Next-Step Recommendations
1. Replace the deterministic comparison stub with the real vector-store + reranker pipeline so delta metrics reflect production behavior.
2. Expand the seed dataset with harder lexical-overlap cases to better separate hybrid retrieval from dense-only retrieval.
3. Add qualitative error analysis for top failure samples to explain when reranking improves ranking and when sparse signals still underperform.
