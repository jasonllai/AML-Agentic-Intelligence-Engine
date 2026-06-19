# AML Data Science and Investigation Redesign Plan

## Goal

Redesign the workbench so the Data Scientist and Investigator roles behave like distinct AML bank functions rather than differently named versions of the same workflow.

The target system should make the Data Scientist role model-driven and mathematically grounded, then hand a ranked, explainable candidate queue to the Investigator role for case-level review, typology mapping, disposition, and feedback.

## Current Implementation Status

This redesign is now implemented in the active codebase. The Data Scientist workflow uses a four-model workbench:

- Isolation Forest.
- Autoencoder.
- Variational Autoencoder.
- Conditional Variational Autoencoder.

The Data Scientist panel does not show report-quality judge cards such as overall judge, faithfulness, citations, or compliance. Those are not model performance metrics and are not appropriate for this workflow.

The Data Scientist workflow may use an LLM only to write readable explanations from deterministic model evidence. The LLM does not determine rank, score, threshold, suspiciousness, or feature drivers. Every LLM-generated candidate explanation is guardrailed before it is returned to the frontend. If guardrail fails, the backend returns a deterministic fallback explanation.

Isolation Forest explanations use model-agnostic SHAP over the actual anomaly-score function for top-ranked candidates. SHAP values select the customer-specific top drivers, while a governed feature dictionary explains each feature's meaning, engineering formula, baseline comparison, and investigator review focus. Autoencoder, VAE, and CVAE candidates expose reconstruction-error contribution. LLM wording may organize this evidence, but deterministic model attribution and feature metadata remain the source of truth.

## Core Assumptions

- The bank-realistic operating model is detection first, investigation second.
- Model output is prioritization evidence, not proof of suspicious activity.
- Investigators, not models, decide whether facts, context, and AML indicators support escalation.
- The active redesign focuses on two roles: `data_scientist` and `investigator`.
- `model_validator` and `compliance_strategy` are not supported roles in the current schema; their concerns are represented through governance, guardrails, and evaluation layers.
- The frontend should remain structurally close to the current workbench. The main change should be fewer, stronger role tasks.
- One realistic task per role is preferable to many weak or redundant tasks.

## Original Design Problem

The pre-redesign system had role labels and route permissions, but the role responsibilities were too similar.

Pre-redesign Data Scientist work was centered on single-customer model explanation and feature critique. That was useful, but incomplete. In a real AML data science team, the role should own the model lifecycle: feature engineering, model training, model comparison, threshold tuning, population scoring, ranked alert generation, explainability, monitoring, and feedback analysis.

Pre-redesign Investigator work was closer to case review, but it was not clearly downstream from a model-driven detection handoff. The Investigator should consume a ranked candidate package from Data Science, then perform evidence review, typology mapping, disposition, and feedback.

## Target Role Contracts

### Data Scientist

Purpose: build, evaluate, tune, and explain AML detection models that prioritize customers or alerts for investigation.

The Data Scientist role should own:

- Feature engineering from transactions, KYC, counterparty/network summaries, geography, channel usage, velocity, peer group behavior, and historical outcomes.
- Model training and scoring across the eligible customer population.
- Model comparison across at least these AML-relevant model families:
  - Isolation Forest.
  - Autoencoder.
  - Variational Autoencoder.
  - Conditional Variational Autoencoder.
- Mathematical validation of each model objective, scoring method, loss function, threshold rule, and explanation method.
- Threshold calibration and alert-volume control.
- Ranked suspicious-candidate generation.
- Explanation of the top ranked customers using feature drivers and model-specific evidence.
- Handoff package generation for investigators.
- Monitoring model drift, feature drift, alert yield, and investigator feedback.

The Data Scientist role should not own:

- Typology conclusions.
- STR filing decisions.
- Case disposition.
- Final investigation narrative.
- Conclusive statements that a customer is laundering money.

Primary role task:

```text
Generate model-driven investigation candidates
```

Expected output:

- Model run summary.
- Candidate ranking table for each of the four models.
- Intersection list for customers appearing in all four top-10 lists.
- Model comparison based on unsupervised diagnostics only.
- Threshold and alert-volume rationale.
- Guarded explanation package for each selected candidate.
- Limitations and uncertainty.
- Investigator handoff package.

### Investigator

Purpose: review model-prioritized candidates, assess facts and context, map typology indicators carefully, and produce a case disposition.

The Investigator role should own:

- Reviewing the Data Scientist handoff package.
- Inspecting transactions, KYC profile, expected behavior, counterparties, geography, channel usage, prior alerts, and available customer context.
- Assessing whether model drivers are supported by transactional evidence.
- Mapping observed activity to AML typology indicators with careful, non-conclusive language.
- Identifying missing evidence and plausible legitimate explanations.
- Producing a disposition such as close, monitor, escalate, or prepare reportable-suspicion narrative for human approval.
- Returning structured feedback to Data Science, including false-positive reason, useful model drivers, missing features, typology labels, and final outcome.

The Investigator role should not own:

- Model training.
- Feature engineering.
- Threshold tuning.
- Model family comparison.
- Mathematical model validation.

Primary role task:

```text
Investigate model-prioritized candidate
```

Expected output:

- Case summary.
- Evidence table.
- Typology indicator mapping.
- Missing evidence and uncertainty.
- Disposition recommendation.
- Feedback fields for model improvement.

## Data Scientist to Investigator Handoff

The explicit boundary between roles should be a governed object called:

```text
Detection Candidate Package
```

Minimum fields:

- `candidate_id`
- `customer_id`
- `model_run_id`
- `model_version`
- `model_family`
- `rank`
- `score`
- `score_percentile`
- `threshold`
- `threshold_reason`
- `alert_recommendation`
- `top_feature_drivers`
- `feature_driver_explanations`
- `supporting_transaction_slices`
- `peer_group_baseline`
- `model_limitations`
- `missing_data`
- `suggested_investigation_focus`
- `disclaimer`

Required disclaimer:

```text
This model output is used for AML investigation prioritization only. It is not proof of suspicious activity and does not by itself support an STR decision.
```

Investigator feedback fields:

- `case_disposition`
- `typology_assessment`
- `false_positive_reason`
- `useful_model_drivers`
- `misleading_model_drivers`
- `missing_features`
- `investigator_notes`
- `label_for_model_evaluation`

## Model Families and Mathematical Validity Requirements

The backend should treat model math as a first-class design requirement, not as implementation detail hidden behind a score.

All four model services must return normalized scores in `[0, 1]`, top-10 ranked candidates, threshold labels, model-specific feature drivers, and a required disclaimer. Incompatible artifacts must fail loudly. For the local prototype, missing deep-learning artifacts may be trained deterministically and saved on first use so the workbench remains runnable; production deployment should replace this with an explicit governed training job.

### Isolation Forest

Required mathematical documentation:

- Random partitioning objective.
- Expected path length intuition.
- Anomaly score derivation.
- Score normalization.
- Threshold calibration rule.
- Why shorter path length implies higher anomaly likelihood.

Required tests:

- Deterministic training with fixed random seed.
- More isolated synthetic outliers receive higher scores than dense-cluster points.
- Score range stays bounded.
- Threshold rule produces expected alert labels.
- Top feature driver extraction is stable for controlled rows.

### Autoencoder

Required mathematical documentation:

- Encoder function.
- Decoder function.
- Reconstruction loss, such as mean squared error over standardized features.
- Anomaly score as reconstruction error.
- Normalization and thresholding.
- Why high reconstruction error indicates poor fit to learned normal behavior.

Required tests:

- Reconstruction error is non-negative.
- Identical input and reconstruction produce zero or near-zero loss.
- Injected outlier rows produce higher reconstruction loss than normal rows in a controlled fixture.
- Standardization is applied consistently during training and inference.
- Missing or reordered features fail loudly.

Implementation requirement:

- Use PyTorch for the encoder/decoder network.
- Use standardized customer features.
- Use per-feature squared reconstruction error to explain candidate drivers.

### Variational Autoencoder

Required mathematical documentation:

- Encoder distributions for latent mean and variance.
- Reparameterization trick.
- Reconstruction term.
- KL divergence term.
- Evidence lower bound objective.
- Anomaly score based on reconstruction error, negative ELBO, or a documented combination.
- Why the chosen score is valid for AML anomaly prioritization.

Required tests:

- KL divergence is non-negative for controlled latent distributions.
- Reparameterized latent samples have expected shape.
- Loss combines reconstruction and KL terms as documented.
- Score is deterministic when seeded or sampling is disabled for evaluation.
- Outlier fixture receives higher anomaly score than normal fixture.

Implementation requirement:

- Use PyTorch for the encoder, latent mean, latent log variance, reparameterization, and decoder.
- During deterministic scoring, use latent mean rather than random latent sampling.
- Use reconstruction error plus KL divergence as the anomaly score basis.

### Conditional Variational Autoencoder

Required mathematical documentation:

- Conditioning variables, such as customer segment, channel mix, jurisdiction group, or KYC type.
- Conditional encoder and decoder inputs.
- Conditional ELBO.
- Score interpretation within condition or peer group.
- Why conditioning reduces false positives from heterogeneous customer populations.

Required tests:

- Condition vectors are encoded deterministically.
- Same transaction features under different valid conditions can produce different expected reconstruction behavior.
- Unknown condition handling is explicit and tested.
- Conditional score is compared against the correct peer/condition baseline.
- Outlier fixture within a condition receives higher score than normal fixture within the same condition.

Implementation requirement:

- Use PyTorch for conditional encoder/decoder inputs.
- Use customer type as the first supported condition: `individual`, `smallbusiness`, or `unknown`.
- Explain candidates against the active condition/peer group.

## LLM Explanation and Guardrail Requirements

For each top-10 candidate in each model output, the backend should pre-generate a concise explanation from deterministic model evidence.

LLM input must be limited to:

- `customer_id`
- `model_family`
- `rank`
- `score`
- `threshold`
- `alert_recommendation`
- `top_feature_drivers`
- `model_specific_driver_details`
- `model_limitations`
- required disclaimer

LLM output must be structured as:

- `summary`
- `model_reasoning`
- `feature_driver_explanation`
- `suggested_investigator_focus`
- `limitations`

Guardrail must run on every LLM explanation. It must block or replace explanations that introduce typology conclusions, STR/legal conclusions, or language implying the model proves suspicious activity.

The frontend should show only guardrail status for the candidate explanation. It must not show judge score cards in the Data Scientist workbench.

## Recommended Backend Architecture Changes

### 1. Split Role Workflows from Agent Capabilities

Keep agents as reusable capabilities, but make role workflows business-specific.

Recommended capability ownership:

| Capability | Data Scientist | Investigator |
| --- | --- | --- |
| Feature engineering | Owns | Consumes only |
| Model training | Owns | No access |
| Model comparison | Owns | No access |
| Population scoring | Owns | Consumes selected candidates |
| Candidate explanation | Owns initial model explanation | Reviews and challenges |
| Transaction behaviour | Uses for feature diagnostics | Owns case evidence review |
| Typology mapping | No conclusion ownership | Owns careful mapping |
| Case disposition | No ownership | Owns |
| Feedback labels | Consumes | Produces |

### 2. Replace Many Role Tasks with One Strong Task Each

Backend task catalog should move toward:

```text
data_scientist: generate_model_driven_candidates
investigator: investigate_model_prioritized_candidate
```

The current tasks can be deprecated or kept internally until frontend and evaluation tests are migrated.

### 3. Add Model Registry-Like Metadata

Even if artifacts remain local files in v1, each model run should record:

- `model_run_id`
- `model_family`
- `model_version`
- feature schema hash
- training data date range
- training customer count
- feature count
- threshold
- threshold method
- evaluation metrics
- random seed
- artifact paths
- limitations

### 4. Add Population Scoring

The current scoring service should be extended from single-customer scoring to population scoring.

Required output:

- score for each modeled customer
- percentile rank
- threshold flag
- top feature drivers
- model version
- candidate rank
- explanation metadata

### 5. Add Model Comparison

The Data Scientist workflow should compare available model families using metrics appropriate to sparse AML labels.

Minimum metrics:

- precision at K
- recall at K when labels exist
- alert volume at threshold
- positive-label capture rate
- score stability
- feature driver coverage
- missing feature rate
- runtime
- calibration summary

Important constraint:

Sparse labels should not be used to overclaim supervised performance. With very few positive labels, labels should be used for calibration sanity checks, rank inspection, and feedback-loop evaluation rather than strong claims of production accuracy.

### 6. Add Candidate Package Generation

Create a backend service responsible for converting ranked model scores into investigator-ready candidate packages.

The package should be explicit about:

- why the candidate was prioritized
- what model features drove the ranking
- what evidence supports the features
- what evidence is missing
- what the investigator should review next
- what conclusions are prohibited

### 7. Add Investigator Case Review Flow

Investigator workflow should accept a `candidate_id` or `customer_id` plus candidate package context.

It should produce:

- behavior review
- typology mapping
- evidence table
- missing evidence
- disposition recommendation
- structured feedback to the model team

### 8. Convert Model Validator into a Governance Layer

Do not delete model validation as a concept.

Instead:

- move model validation checks into evaluation and governance tests
- expose validation status in model metadata
- keep model validation reports as backend artifacts
- remove it as a redundant primary role unless the user later wants a dedicated governance workspace

### 9. Park Compliance Strategy

Compliance strategy should not be part of the first redesign.

Keep typology knowledge and compliance-safe language inside investigator guardrails and RAG, but avoid a separate strategist role until the detection-to-investigation loop is realistic.

## Recommended Frontend Changes

The frontend should not be redesigned heavily.

Keep the current workbench layout, but simplify role tasks:

```text
Data Scientist
Task: Generate model-driven investigation candidates

Investigator
Task: Investigate model-prioritized candidate
```

Recommended UI behavior:

- Data Scientist page shows model family selection, threshold or top-K input, model comparison summary, ranked candidate table, and candidate package preview.
- Investigator page shows selected candidate package, transaction evidence, typology mapping, disposition controls, and feedback fields.
- Model Validator and Compliance Strategy should be hidden, disabled, or clearly marked as future/governance views.
- Route preview should show business workflow steps rather than many abstract agents.
- Reports should distinguish model handoff report from investigation case report.

Chrome requirement for frontend work:

- After backend changes are complete and frontend changes are made, use `chrome:control-chrome` to inspect the running local frontend.
- Verify that each role presents one strong task.
- Verify that labels, report sections, and route previews match the redesigned operating model.
- Verify that the UI has not become more complex than the original.
- Verify that the frontend output reflects backend results rather than hardcoded role text.

## Test Strategy

Testing must be broad enough to make the redesigned system grounded.

### Unit Tests

Required coverage:

- feature schema consistency
- model mathematical helper functions
- score normalization
- thresholding
- candidate ranking
- candidate package construction
- role-task routing
- role permission boundaries
- investigator feedback schema

### Model Math Tests

Each model family must have tests that verify the mathematical objective used by the implementation.

Tests should prove:

- losses are computed correctly on controlled inputs
- scores move in the expected direction
- feature ordering is enforced
- invalid feature schemas fail loudly
- seeded runs are deterministic where required
- documented thresholds match implementation behavior

### Integration Tests

Required flows:

- Data Scientist can run population scoring and receive ranked candidates.
- Candidate package includes score, rank, threshold, top drivers, limitations, and disclaimer.
- Investigator can consume a candidate package and produce a case disposition.
- Investigator feedback is captured in structured form.
- Investigator cannot trigger training or threshold tuning.
- Data Scientist cannot produce typology conclusions or case disposition.
- Deprecated tasks either fail clearly or route only through intended compatibility paths.

### Evaluation / Golden Dataset Tests

Update the golden dataset so it reflects the new role model.

Required cases:

- high-ranked candidate with clear model drivers
- low-ranked customer below threshold
- missing customer
- missing model artifacts
- sparse-label evaluation case
- prompt injection in investigator query
- typology mapping with required careful language
- candidate package missing disclaimer
- investigator feedback with false-positive reason

### Frontend Verification

After backend and frontend work:

- Run backend tests.
- Run frontend type/lint checks if available.
- Start the local app.
- Use Chrome to verify the two role workflows visually and functionally.
- Capture any mismatch between backend design and frontend labels in the iteration log.

## Iteration and Mistake Documentation Requirement

During implementation, maintain an execution log so future work can avoid repeating mistakes.

Recommended file:

```text
docs/AML_REDESIGN_ITERATION_LOG.md
```

The log should be updated after each significant checkpoint.

Required entry format:

```markdown
## YYYY-MM-DD HH:MM - Checkpoint Name

What changed:
- Use concrete bullets naming the files, behavior, or test cases changed.

What was verified:
- Name the exact command, test, manual check, or Chrome verification performed.

Mistakes or wrong assumptions:
- State the incorrect assumption or failed attempt plainly. Write `None observed` only if no issue occurred.

Correction:
- Explain the correction made and why it resolves the issue.

Lesson for similar future work:
- Capture the reusable lesson that should prevent the same mistake later.
```

Log entries are required when:

- a test fails for a nontrivial reason
- a design assumption proves wrong
- a model metric or score behaves unexpectedly
- an implementation has to be simplified
- frontend verification exposes a mismatch
- any previous plan step is changed

No mistake should be hidden. If something was misunderstood, document it plainly and explain how the correction prevents recurrence.

## Execution Sequence

### Phase 1: Role and Task Contract

Success criteria:

- Backend role catalog exposes one primary task for Data Scientist and one for Investigator.
- Redundant role tasks are removed, hidden, or explicitly deprecated.
- Tests verify role-task boundaries.

### Phase 2: Model Math Foundation

Success criteria:

- Isolation Forest math is documented and tested.
- Autoencoder, VAE, and CVAE interfaces are designed with explicit objectives and losses.
- Any model family not fully implemented yet fails clearly rather than pretending to work.
- Tests cover mathematical helper functions and score directionality.

### Phase 3: Population Scoring and Candidate Ranking

Success criteria:

- Data Scientist workflow scores the modeled population.
- Ranked candidates are generated with top drivers and threshold rationale.
- Sparse labels are used carefully for evaluation and calibration checks.
- Tests verify candidate ordering and threshold behavior.

### Phase 4: Candidate Package Handoff

Success criteria:

- Detection Candidate Package is produced for each selected candidate.
- Package includes disclaimer, limitations, top drivers, evidence slices, and investigation focus.
- Tests verify package completeness and prohibited conclusion handling.

### Phase 5: Investigator Case Review

Success criteria:

- Investigator workflow consumes a candidate package.
- Output includes evidence review, typology mapping, missing evidence, disposition, and feedback.
- Tests verify investigators cannot perform model-development actions.

### Phase 6: Evaluation Framework Update

Success criteria:

- Golden dataset reflects the new role contracts.
- Evaluation metrics include route correctness, candidate package completeness, model math checks, compliance-safe language, and feedback capture.
- Missing artifacts and missing customer cases fail loudly and safely.

### Phase 7: Frontend Simplification

Success criteria:

- Frontend keeps the current layout but presents one strong task per role.
- Data Scientist UI centers on model run, ranking, and handoff.
- Investigator UI centers on candidate review, typology mapping, disposition, and feedback.
- Model Validator and Compliance Strategy are removed from the primary role list or marked as future governance views.

### Phase 8: Chrome-Based Frontend Verification

Success criteria:

- Chrome inspection confirms the local app matches the redesigned role model.
- No redundant tasks are visible for the two main roles.
- Reports and route previews use business language rather than redundant agent names.
- Any mismatch is documented in the iteration log before final completion.

## Non-Goals

- Do not build a production-grade model registry in the first pass.
- Do not claim bank production readiness.
- Do not automate STR decisions.
- Do not make model validation disappear as a governance concern.
- Do not redesign the frontend from scratch.
- Do not add extra roles until Data Scientist and Investigator are clearly differentiated.

## Public Grounding References

- FINTRAC suspicious transaction reporting guidance: use facts, context, and ML/TF indicators before reaching reportable suspicion. This supports the boundary that model output is prioritization, not proof.
  - https://fintrac-canafe.canada.ca/guidance-directives/transaction-operation/str-dod/str-dod-eng
- FATF new technologies for AML/CFT: AI/ML can improve risk identification and prioritization, but responsible use requires explainability, auditability, governance, and human expert review.
  - https://www.fatf-gafi.org/content/dam/fatf/documents/reports/Opportunities-Challenges-of-New-Technologies-for-AML-CFT.pdf
- OSFI Guideline E-23 Model Risk Management, 2027: model development, review, monitoring, validation, and governance responsibilities must be explicit for AI/ML model use in Canadian financial institutions.
  - https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027
- AML alert optimization research: machine learning can be used to rank and prioritize AML alerts, which supports the Data Scientist to Investigator candidate-handoff model.
  - https://arxiv.org/abs/2112.07508

## Final Acceptance Criteria

The work is complete only when:

- Data Scientist produces model-driven ranked candidates, not case investigation conclusions.
- Investigator consumes candidates and produces evidence-based case review, not model-development output.
- Isolation Forest, Autoencoder, VAE, and CVAE expectations are represented in backend design with mathematical validity requirements.
- Implemented model math is tested with controlled cases.
- Candidate package handoff is explicit and tested.
- The frontend shows one strong, realistic task per role.
- Chrome verification confirms the UI matches backend behavior.
- The iteration log documents improvements, wrong turns, corrections, and lessons learned.
