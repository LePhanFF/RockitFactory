# Phase 4: Training Pipeline — Detailed Roadmap

> **Goal:** Automated LoRA training with evaluation gates and model registry.
> **Duration:** Week 8-11 (overlaps with Phase 3)
> **Depends on:** Phase 1 (deterministic modules for data generation)
> **Blocks:** Phase 5a (agent system needs trained model)

---

## Tasks

### 4.1 Port training scripts
- [ ] `generate_training_data_with_synthetic_output.py` → `rockit-train/dataset.py`
- [ ] `generate_lora_training_data.py` → `rockit-train/trainer.py`
- [ ] Ensure training data uses all 259+ sessions (not just 90)

### 4.2 Model registry
- [ ] Set up GCS bucket for model versions
- [ ] Implement registry: version, config hash, eval metrics, promotion status
- [ ] MLflow experiment tracking integration

### 4.3 Incremental LoRA training
- [ ] Train on new data only, keep previous adapter as starting point
- [ ] Test with Qwen 3.5 32B on DGX Spark

### 4.4 Full retrain
- [ ] Train from base model with all data
- [ ] Multi-model configs (30B, 70B)

### 4.5 Holdout evaluation set
- [ ] Create 50-session holdout set (never trained on)
- [ ] Balanced: 10 Trend, 10 P-Day, 10 B-Day, 10 Neutral, 10 edge cases
- [ ] Implement automated evaluation: day_type_accuracy, bias_accuracy, calibration, schema compliance

### 4.6 Evaluation gates
- [ ] New model must match or beat baseline on ALL metrics
- [ ] Automated comparison report
- [ ] Auto-deploy if all gates pass, with 5-day canary period

### 4.7 End-to-end pipeline test
- [ ] `make train CONFIG=configs/training/qwen-30b.yaml MODE=incremental`
- [ ] Verify: strategy change → data regen → train → eval → register

---

## Definition of Done

- [ ] Incremental LoRA training completes successfully
- [ ] Full retrain with Qwen 30B completes successfully
- [ ] Evaluation gates block a deliberately degraded model
- [ ] Model registry stores versions with full lineage
- [ ] LLM quality metrics logged at every evaluation (FAQ Q18 Layer 4)
