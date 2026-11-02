# Sports Buddy

Football goal-market and result probabilities for 40 competitions, with a **Suggested picks** panel that ranks the
most likely options across every competition on the day. Probabilities come from a walk-forward model
(team ratings + form + a logistic layer) trained on ~10 years of results.

> Honest note: in backtests the bookmakers' own prices were at least as accurate as this model, and betting its
> "edge" lost money on average. Treat probabilities as a reference, not a tip. Never stake more than you can afford to lose.

## Optional: live API on Render

The site works WITHOUT this (see "saved data only" below, which is the default). Only add Render if you really need on-demand data.

1. render.com > **New + > Blueprint** > pick this repo. Edit `ALLOWED_ORIGINS` in `render.yaml` to your own `https://<username>.github.io` first.
2. Type your `API_FOOTBALL_KEY` when asked (it stays in Render, never in the repo). Use a key different from the GitHub one if your plan allows.
3. Put the service address in `docs/config.js`: `apiBase: "https://<service>.onrender.com"`.

Account-safety rules built into the server (see `app/services/sports_api.py`): answers are cached, there is a hard daily budget (`API_DAILY_BUDGET`) and per-minute limit, calls pause automatically if the provider answers 429/403 or says you are nearly out, only dates within a few days of today can reach the provider, there is no background job calling the provider, and `/docs` plus the live-score/fixture-lookup routes are switched off (`ENABLE_DOCS=1` / `ENABLE_EXTRA_ENDPOINTS=1` turn them on for local use only).

## Use it as a website with saved data only (no server)
1. Push this folder to a GitHub repository. The model's history is ONE file, `data/historical/matches.csv.gz` (2.6 MB), so you do not need to upload the 280 raw CSVs. `.env` is ignored.
2. Repo **Settings > Secrets and variables > Actions > New secret**: name `API_FOOTBALL_KEY`, value = your key.
3. Repo **Settings > Pages**: deploy from branch `main`, folder `/docs`.
4. **Actions > Daily predictions > Run workflow** once. After that it runs every morning by itself
   (refreshes yesterday's results, predicts today and tomorrow, scores yesterday, updates `docs/`).
5. Open `https://<your-username>.github.io/<repo>/`.

The site is static: it reads `docs/data/<date>.json`. Odds you type are stored in your own browser.

## Run it on your computer (optional)
    pip install -r requirements-dev.txt
    uvicorn app.main:app --reload          # then open frontend/index.html with VS Code Live Server
    python build_site.py                   # regenerate docs/ by hand
    python today.py                        # command-line table
    python score_day.py --date YYYY-MM-DD  # compare saved predictions with results
    python -m pytest -q                    # tests
    python backtest_v4.py                  # re-train + honest backtest report

## Files you may want to edit
- `data/team_aliases.json`: `{"provider spelling": "csv spelling"}` when a team name is not recognised.
- `data/today/fixtures_<date>.csv`: extra fixtures, e.g. Champions League with `PH,PD,PA` win percentages.
