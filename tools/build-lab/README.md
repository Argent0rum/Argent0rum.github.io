# Build Lab data and updater

Build Lab (the Genshin / Star Rail build tool) lives as a private Claude artifact. This folder keeps its source
and its game data, so both are backed up and the data can refresh itself.

- `data/hsr.json`, `data/genshin.json`: the game data the tool reads.
- `update.py`: adds characters, weapons / light cones and gear sets that are new in the public data sources
  (StarRailRes for Star Rail, the genshin-db package for Genshin). It never changes or removes existing
  entries. New characters get real stats and skill numbers; their build advice is estimated from the kit and
  labelled as an estimate.
- `page/`: the page itself (`index.html`, `backup.js`), as last published.
- `last_update.txt`: what the last run added.

A GitHub Action runs `update.py` every Monday and commits anything new (free, no Claude usage). The artifact
cannot download from GitHub by itself, so to get the new data into the tool, tell Claude "update Build Lab":
it copies `data/*.json` from here into the artifact.

Run by hand: `python tools/build-lab/update.py` (add `--check` to compare existing entries with the sources).
