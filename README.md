# Rajasthan Royals pressure scouting

Extract this project and double-click **dist/dashboard.html**. The complete dashboard runs locally in a modern desktop or mobile browser. The data, styles, scripts and PDF are embedded. No installation or web service is needed for the prebuilt version.

## Rebuild with the original ZIP

Use Python 3.12. In the extracted project directory, run:

    python -m pip install -r requirements.txt
    python build.py "path/to/6af458274c1e8_data_pack.zip"

The source archive stays on your computer. The builder writes dist/dashboard.html, dist/methodology.pdf, dist/batters.csv and dist/bowlers.csv. If you want to serve the result locally, run python -m http.server 8000 --directory dist and visit http://localhost:8000/dashboard.html.

## Project layout

- build.py reads the match, competition and delivery files from the ZIP, creates pre-delivery features, computes context-adjusted rankings and robustness checks, and exports the dashboard, report and shortlists.
- app.js implements overview, rankings, player detail, comparison and methodology in browser-native JavaScript. It uses hash routes and works when opened from disk.
- style.css and template.html define responsive presentation.
- dist contains ready-to-use outputs. The raw franchise archive is excluded.

## Use the dashboard

Start with either official top 10, then select a player. The pressure rate, comparable personal baseline lift, 90% interval, match observations, IPL-only rank and season sensitivity help interpret the shortlist. Filtering the rankings switches to descriptive split statistics while preserving the official ranking as a reference. The full eligible field sits below the unfiltered top 10. Methodology includes all scoring assumptions and downloads.

## Interpreting the results

The rank is a model result, not a confirmed auction recommendation. IPL-only eligibility is useful for interpreting a T20I-heavy score. No auction availability, price or retention data is supplied. The dominant pressure phase describes usage and is a starting point for role assessment. The 12-run wicket value and pressure thresholds are analyst assumptions. The model compares historical outcomes across contexts; it does not predict a 2027 season or adjust for opponent quality.

For exact criteria, see METHOD, summarize() and rate() in build.py. Pressure is tagged before delivery outcomes enter the performance calculation. First-innings par uses earlier dates only. Peer and player performance baselines use the analysed historical sample retrospectively. Players must meet both ordinary-ball and pressure-ball criteria. Positive match lift counts as above baseline. Uncertainty bands are for lift, not for rank.
