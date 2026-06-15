# AML Redesign Iteration Log

## 2026-06-07 17:40 - Baseline Setup

What changed:
- Created the redesign iteration log before implementation work.
- Switched from `main` to `codex/aml-redesign` so implementation does not happen directly on `main`.
- Installed backend dev dependencies declared in `aml_agentic_workbench/backend/pyproject.toml` because baseline tests could not import `psycopg`.

What was verified:
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 57 passed.
- `pnpm typecheck` from `aml_agentic_workbench/frontend` passed.

Mistakes or wrong assumptions:
- Initial baseline assumption that the Python environment already had all declared backend dependencies was wrong.

Correction:
- Installed the backend project with dev extras using `python -m pip install -e '.[dev]'`.

Lesson for similar future work:
- Run baseline tests before implementation and distinguish missing environment dependencies from product failures.

## 2026-06-07 17:45 - Role Contract and Math Foundation

What changed:
- Added tests for the new primary role tasks, route boundaries, candidate package disclaimer, investigator feedback schema, and model math helpers.
- Added deterministic math helpers for Autoencoder, VAE, and CVAE objectives.
- Added new candidate handoff schemas and new router constants/routes for candidate ranking and case investigation workflows.

What was verified:
- `python -m pytest app/tests/test_aml_redesign_contracts.py app/tests/test_model_math_foundation.py -v` passed: 11 passed.

Mistakes or wrong assumptions:
- The first CVAE test used exact equality for `0.7 - 0.2`, which failed due to floating-point precision.

Correction:
- Changed the assertion to `pytest.approx(0.5)`.

Lesson for similar future work:
- Mathematical tests should be strict about behavior but use approximate comparisons for floating-point arithmetic.

## 2026-06-07 17:58 - Candidate Workflow Backend

What changed:
- Added population scoring through `ModelService.score_population`.
- Added `CandidateGenerationService` to build Detection Candidate Packages and investigator case feedback.
- Added deterministic `candidate_ranking_agent` and `case_investigation_agent` graph nodes.
- Added API result fields for `model_run_summary`, `candidate_packages`, and `investigation_case_review`.
- Vectorized Isolation Forest scoring so population ranking no longer loops through one customer scoring call at a time.

What was verified:
- `python -m pytest app/tests/test_candidate_workflows.py -v` passed: 4 passed.
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 72 passed.

Mistakes or wrong assumptions:
- The first endpoint test run exposed that per-customer population scoring was too slow for an interactive workflow.
- A standalone endpoint call outside pytest took 141.68 seconds because the local `.env` selected the real LLM client rather than the mock client.

Correction:
- Reworked population scoring to score the feature matrix in bulk and build detailed explanations only for top candidates.
- For later local end-to-end verification, use mock LLM settings so frontend checks validate the redesigned workflow without external LLM latency.

Lesson for similar future work:
- Green tests are not sufficient when a workflow is interactive; measure runtime on representative paths and keep external LLM calls controlled during verification.

## 2026-06-07 18:06 - Evaluation Dataset Alignment

What changed:
- Updated the golden dataset role/task catalog so Data Scientist and Investigator evaluation cases use the new primary tasks.
- Added evaluation tags for candidate packages and investigator feedback.
- Kept Model Validator and Compliance Strategy as governance/evaluation coverage rather than primary UX targets.

What was verified:
- `python -m pytest app/tests/test_system_evaluation.py::test_golden_dataset_covers_roles_tasks_and_edge_cases -v` passed.
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 72 passed.

Mistakes or wrong assumptions:
- Introduced an unused route variable while changing golden dataset edge cases.

Correction:
- Removed the unused route and reused the investigator route for both missing-customer and prompt-injection edge cases.

Lesson for similar future work:
- Evaluation fixture changes should be reviewed for dead variables because they often evolve through small route substitutions.

## 2026-06-07 18:14 - Frontend Role Simplification

What changed:
- Updated frontend API types for model run summaries, detection candidate packages, and investigation case reviews.
- Reduced the visible primary role catalog to Data Scientist and Investigator.
- Updated role catalog copy so each primary role has one strong task.
- Simplified the role workspace request form and route preview language.
- Added report panels for candidate packages and investigator feedback.

What was verified:
- `pnpm typecheck` from `aml_agentic_workbench/frontend` passed.

Mistakes or wrong assumptions:
- Initially reused a dark-sidebar status component inside a white report card, which would have made text hard to read.
- Initial report helper type guards treated optional top-level fields as discriminators, which TypeScript correctly rejected.

Correction:
- Added a light-card `FeedbackLine` component for investigator feedback.
- Switched report helper type guards to use `"result" in report`.

Lesson for similar future work:
- Reusing UI microcomponents across dark and light surfaces needs a visual contrast check, and optional fields should not be used as TypeScript discriminators.

## 2026-06-07 - Final Backend, Frontend, and Chrome Verification

What changed:
- Added a narrow local keyword typology fallback for the primary investigator handoff task when pgvector is unavailable.
- Added a regression test proving the primary investigator route completes locally while legacy selected typology routes still fail loudly with the pgvector operator action.
- Added candidate-card handoff links from Data Scientist output to the Investigator workspace and prefilled the selected customer ID from the handoff URL.

What was verified:
- `python -m ruff check app` from `aml_agentic_workbench/backend` passed.
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 74 passed.
- `pnpm typecheck` from `aml_agentic_workbench/frontend` passed.
- `pnpm build` from `aml_agentic_workbench/frontend` passed.
- Live API checks returned 200 for `generate_model_driven_candidates` and `investigate_model_prioritized_candidate`.
- Chrome verification loaded `http://127.0.0.1:3001/roles`, confirmed only Data Scientist and Investigator are primary role cards, ran Data Scientist candidate generation, followed the top candidate handoff to Investigator, and ran Investigator case review with feedback.

Mistakes or wrong assumptions:
- The full investigator browser flow initially failed because the new primary route still depended on pgvector typology retrieval in a clean local environment.
- Running `next build` while the dev server was active invalidated the dev server chunk cache; Chrome loaded SSR HTML without attached CSS/JS, so UI clicks did not trigger React handlers.
- `pnpm lint` is not configured; Next.js prompts to create an ESLint config and exits instead of running a lint pass.

Correction:
- Kept legacy pgvector failure behavior intact, but allowed the primary investigator handoff task to use local keyword retrieval with an explicit fallback limitation.
- Restarted the frontend dev server after clearing the generated `.next` directory before Chrome verification.
- Reported lint as unavailable rather than silently adding project lint configuration outside the redesign plan.

Lesson for similar future work:
- End-to-end browser verification should start from a fresh dev server after production builds, and local dependency fallbacks must be tested at the exact role/task boundary that users exercise.

## 2026-06-07 - Four-Model Data Scientist Workbench Verification

What changed:
- Updated the redesign plan to specify the four-model Data Scientist workbench, guarded LLM explanations, and prototype artifact behavior.
- Implemented four Data Scientist model result sets: Isolation Forest, Autoencoder, Variational Autoencoder, Conditional Variational Autoencoder, plus an intersection list.
- Added guarded LLM explanation generation for top-ranked candidates while keeping score, rank, threshold, and feature drivers deterministic.
- Removed Data Scientist judge-score presentation and kept the frontend focused on model run, dropdown model selection, expandable candidates, and investigator handoff.
- Declared PyTorch as a backend dependency because the Autoencoder, VAE, and CVAE services import and run PyTorch models.

What was verified:
- `python -m ruff check app` from `aml_agentic_workbench/backend` passed.
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 77 passed.
- `pnpm typecheck` from `aml_agentic_workbench/frontend` passed.
- `pnpm build` from `aml_agentic_workbench/frontend` passed.
- Chrome loaded `http://127.0.0.1:3001/roles/data_scientist` and confirmed the Data Scientist page has no Customer ID input, no workflow instruction box, no Current workflow section, and no workflow preview section.
- Chrome ran the Data Scientist workflow against the local backend and confirmed the result view has all four model options plus intersection, no Overall judge/Faithfulness/Citations/Compliance cards, expandable candidate rows, guarded explanation text, feature drivers, model limitations, score, threshold, required disclaimer, and visible guardrail fallback status.
- Chrome switched the dropdown to Autoencoder and Intersection and confirmed the candidate list changed.
- Chrome followed the handoff to Investigator and confirmed `customerId=SYNID0200567030&modelFamily=intersection` in the URL, the customer input was prefilled, and the investigator instruction preserved the model context.

Mistakes or wrong assumptions:
- Initially left the frontend Data Scientist route preview with only the candidate-ranking step even though the backend executes the mandatory guardrail step.
- The first Chrome reload hit the same stale `.next` webpack-runtime failure after prior builds.
- Long in-page Chrome polling timed out because this Chrome runtime limits read-only evaluate calls to short CDP windows.
- Live LLM explanation calls can take roughly one minute for 40 top-candidate explanations even with per-model candidate concurrency.

Correction:
- Updated the Data Scientist frontend route to show both `candidate_ranking_agent` and `guardrail_agent`.
- Cleared the generated `.next` directory and restarted the frontend dev server before browser verification.
- Switched Chrome verification from long in-page polling to backend log observation plus short DOM reads.
- Kept live LLM usage for the browser run but tests use the deterministic mock LLM.

Lesson for similar future work:
- Browser verification should use short, stable DOM reads and should not rely on long page-context polling. When a workflow calls a real LLM many times, keep CI deterministic with mocks and record live latency as an operational limitation.

## 2026-06-07 - SHAP Isolation Forest Explanation Upgrade

What changed:
- Added a model-agnostic SHAP explanation layer for the custom local Isolation Forest score function.
- Added a feature dictionary for the real-data AML feature schema so driver cards explain feature meaning, engineering formula, investigator interpretation, and evidence to review.
- Changed Isolation Forest top drivers from absolute standardized deviation to per-customer absolute SHAP contribution, while retaining value, baseline, and z-score context.
- Improved candidate fallback explanations so they remain useful when LLM output is blocked.
- Added candidate-specific guardrails so safe model explanation wording can pass while prohibited conclusions still fall back.
- Updated the Data Scientist candidate row UI to show feature meaning, value versus baseline, SHAP contribution, standardized deviation, and investigator focus.
- Renamed raw guardrail labels in the UI to `LLM Passed`, `Safe Fallback`, and `LLM Unavailable`.

What was verified:
- `python -m pytest app/tests/test_shap_isolation_explanations.py -q` passed.
- `python -m pytest` from `aml_agentic_workbench/backend` passed: 81 passed.
- `python -m ruff check app` from `aml_agentic_workbench/backend` passed.
- `pnpm typecheck` from `aml_agentic_workbench/frontend` passed.
- `pnpm build` from `aml_agentic_workbench/frontend` passed.
- Chrome loaded the Data Scientist panel, ran the workflow, and confirmed the expanded Isolation Forest row shows SHAP contribution, engineered feature meaning, customer value, population baseline, investigator focus, the required disclaimer, and no generic `contributed to the model prioritization` wording.

Mistakes or wrong assumptions:
- Installing `shap` alone reused an older local `numba`/`llvmlite` build that was incompatible with NumPy 2.0.2.
- SHAP emitted internal arrays at INFO level during the first live backend run.
- The first direct single-customer SHAP implementation would have used only the scored customer as background when a full training population was available.

Correction:
- Added an explicit `numba>=0.62.0` dependency and upgraded the local runtime.
- Suppressed the `shap` logger to warning level.
- Changed single-customer scoring to use the modeled training population as SHAP background when available.

Lesson for similar future work:
- Explainability libraries bring compiled dependency constraints; verify the full import path, not just package installation. SHAP background choice must be reviewed explicitly because a one-row background can make local explanations mathematically weak.
