# Fresh start checklist

1. **New API-Football key** (dashboard.api-football.com). Never paste it in a file in the repo.
2. **New GitHub repo**, upload everything in this folder (the `.gitignore` already blocks `.env`).
3. Repo **Settings > Secrets and variables > Actions > New repository secret**: `API_FOOTBALL_KEY` = your key.
4. Repo **Settings > Pages**: branch `main`, folder `/docs`.
5. **Actions > Daily predictions > Run workflow** once. It then runs every morning by itself (about 4 provider calls a day).
6. Open `https://<username>.github.io/<repo>/`. Done. No Render needed.

Optional Render (live API): see README. Edit `ALLOWED_ORIGINS` in `render.yaml`, and set `apiBase` in `docs/config.js` only after it works.

## Rules that keep the account from being suspended again
- One key per place if your plan allows (GitHub secret, Render, your laptop).
- Do not run `today.py`, `build_site.py` or `download_csvs.py` in a loop, and do not run `uvicorn --reload` with a live key (use a dummy key when only editing the page).
- Keep the repo's `docs/config.js` in static mode unless you really need Render.
- If the site shows "paused", the guard stopped calls on purpose; check `/status` on the server (`provider_usage`).
- If the provider suspends the key again, email their support and ask which request pattern triggered it.
