# joss-cff-census

A census of the `CITATION.cff` files behind every paper in the
[Journal of Open Source Software](https://joss.theoj.org) (JOSS): how many repositories have
one, how many fail the official CFF 1.2.0 schema, how many use a `license` list that Zenodo's
GitHub integration currently rejects
([zenodo/zenodo-rdm#1509](https://github.com/zenodo/zenodo-rdm/issues/1509)), and how many
name a JOSS DOI that belongs to a different paper.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has checked the results. Code Apache-2.0; text and data CC BY 4.0.

## Status

- `PREREG.md`: question, method, nearest prior work and eight predictions, committed
  **before** any census output was read.
- Census 1 is running. Results and a hand grading of every prediction will be added here as
  `results/census1/` and `GRADING-1.md`, including the predictions that fail.

## Run it

```
pip install pyyaml jsonschema
python census.py --out-dir out          # all JOSS repositories (no API key needed)
python census.py --out-dir out --limit 50
python -m unittest -v
```

Outputs: `summary.json` (all counts), `repos.csv` (one row per repository), `foreign.csv`
(JOSS DOIs in core fields that are not the repository's own), `sample_invalid.csv` (the
pre-registered grading sample), `joss_papers.jsonl` and the raw files in `cff/`.

## Limits

- Default branch only, read through raw.githubusercontent.com. A 404 can't tell a missing
  file from a deleted or renamed-away repository, so presence is a lower bound.
- Only files that declare `cff-version: 1.2.0` are checked against the schema; JSON-schema
  `format` keywords are not enforced (the patterns are).
- Non-GitHub repositories (GitLab, Bitbucket and others) are counted and skipped.

## Licence

Apache-2.0 (see `LICENSE`). Text and data: CC BY 4.0.
