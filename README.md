# Casino bonus scraper

Fetches the comparison table on [BetProof's South Africa casino bonus page](https://betproof.co.za/casino-bonuses-south-africa/), selects Hollywoodbets, Betway South Africa and PlayaBets, and uses Gemini structured output to turn each offer's terms into fields. The scraper checks `robots.txt` first, fails if the site disallows access, and does not interact with login pages, CAPTCHAs or access controls.

## Install and run

Requires Python 3.10 or newer and a [Google AI Studio API key](https://aistudio.google.com/apikey). Gemini 2.5 Flash is currently included in Google's free API tier, subject to its rate limits and terms. The free tier may use submitted content to improve Google's products; this scraper sends only public casino bonus text. Do not attach billing if you need to ensure calls cannot become paid.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Add `GEMINI_API_KEY=...` to `.env` using a key created in Google AI Studio. Preserve any existing `.env` entries; never commit this file. Then run:

```powershell
python scraper.py
```

The script writes `bonuses.json` beside itself and makes one Gemini request per casino. `GEMINI_MODEL` is optional; it defaults to `gemini-2.5-flash`. Free-tier availability and quotas can change; a quota error stops the run without replacing the current JSON. See [Google's Gemini API pricing and free-tier details](https://ai.google.dev/gemini-api/docs/pricing).

The public source currently labels its comparison data as verified in March 2026; the scraper records when it fetched the page, not when the source last verified the terms. Confirm offers with the operator before relying on them.

## Web page

Open `index.html` through a local static server (for example, `py -m http.server 8000`) and visit `http://localhost:8000`. It reads `bonuses.json` in the same folder and is suitable for the root of a GitHub Pages repository; commit the JSON output along with the page to publish the data.

## Production note

See [production-plan.md](production-plan.md) for the proposed daily 200-casino deployment, storage, monitoring and cost estimate. The page is not published yet; deployment requires a hosting account and a repository remote.

## Submission status

`bonuses.json` has been generated from the live source and Gemini's free-tier API on 2026-10-12; values were scraped and model-structured, not typed in by hand. The live page remains unpublished: this repository has no configured remote, so publish the page files and JSON to your chosen free static host. The API key is only in the local ignored `.env` file and must not be committed.