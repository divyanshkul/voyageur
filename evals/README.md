# Voyageur evals

A named eval set for the agent pipeline. Runs on every PR via GitHub Actions
and blocks merges if pass rate drops below the committed baseline.

## Run locally

```bash
python -m evals.run_evals                 # everything, fails on regression
python -m evals.run_evals --suite offline # no API keys needed
python -m evals.run_evals --suite online  # needs OPENAI_API_KEY
python -m evals.run_evals --case ranker_budget_fit
python -m evals.run_evals --update-baseline  # after intentional quality change
```

Reports land in `evals/reports/` (gitignored).

## Suites

- **offline** — exercises pure-Python logic: `rank_hotels`, `compare_prices`,
  `normalize_destination`, `validate_preferences`. No network calls. Always
  runs in CI.
- **online** — exercises LLM-dependent agents: `PreferenceAgent`,
  `ReportAgent`. Skipped when `OPENAI_API_KEY` is absent.

## Adding a case

1. Drop a JSON file into `evals/cases/`. Required fields:

   ```json
   {
     "id": "unique_id_snake_case",
     "suite": "offline | online",
     "evaluator": "ranker | pricing | destination | validation | preference | report",
     "description": "one-line description",
     "input":  { ... evaluator-specific ... },
     "expect": { ... evaluator-specific ... }
   }
   ```

2. Any string value matching `{today+Nd}` or `{today-Nd}` is resolved at
   runtime — use it for dates so cases don't go stale.

3. Run `python -m evals.run_evals --case <id>` to confirm it passes.

4. If this case is expected to raise the baseline pass count, run
   `python -m evals.run_evals --update-baseline` and commit the updated
   `baseline.json`.

## Evaluator cheatsheet

| evaluator    | input keys                                   | expect keys                                                |
|--------------|----------------------------------------------|------------------------------------------------------------|
| destination  | `alias`                                      | `canonical`                                                |
| validation   | `preferences`                                | `valid`, `issue_contains[]`                                |
| ranker       | `preferences`, `hotels[]`, `ota_prices{}`    | `top_name`, `top_score_min`, `min_returned`, `excludes[]`  |
| pricing      | `call_results[]`                             | `top_name`, `verdicts_in_order[]`, `savings_percent_min`   |
| preference   | `turns[]`                                    | `extracted`, `preferences.{destination_contains, guests, budget_max_in_range, nights_in_range}` |
| report       | `preferences`, `call_results[]`              | `top_pick_name`, `summary_contains[]`, `markdown_contains[]` |

## Closed loop

When a real run surfaces a regression, capture the minimal reproducing input
as a new case. Cases accumulate — that's the whole point of a named eval
set. Stale cases can be removed but should be replaced, not silently
deleted.
