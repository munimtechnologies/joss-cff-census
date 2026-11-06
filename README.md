# joss-cff-census

A census of the `CITATION.cff` files behind every paper in the
[Journal of Open Source Software](https://joss.theoj.org) (JOSS): how many repositories have
one, how many fail the official CFF 1.2.0 schema, how many use a `license` list that Zenodo's
GitHub integration currently rejects
([zenodo/zenodo-rdm#1509](https://github.com/zenodo/zenodo-rdm/issues/1509)), and how many
name a JOSS DOI that belongs to a different paper.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has checked the results. Code Apache-2.0; text and data CC BY 4.0.

## Results (census 1, 2026-11-06)

Graded in [`GRADING-1.md`](GRADING-1.md) against [`PREREG.md`](PREREG.md): the gate passed and
5 of 8 predictions held.

- 3,787 JOSS papers, 3,573 GitHub repositories: **33.4%** have a `CITATION.cff` (1,192).
- **11.4%** of files that declare cff-version 1.2.0 fail the schema (125 of 1,097). All 30
  sampled failures were confirmed by hand.
- The most common causes are author entries that are neither a person nor an entity (often a
  bare ORCID iD instead of `https://orcid.org/...`), missing top-level `authors`/`title`
  (citation-only files), and `publisher: "The Open Journal"` written as a string (17 files).
- Only 4 files (0.34%) use a `license` list; 2 of them have no `.zenodo.json`.
- 80.8% name their own JOSS DOI.
- The 3 "foreign" JOSS DOIs were all moved projects asking to be cited by their newer JOSS
  paper, not errors. The census did not merge renamed repositories, and that is a known limit.

Data: [`results/census1/`](results/census1/) (`summary.json`, `repos.csv`, `foreign.csv`,
`sample_invalid.csv`, `joss_papers.jsonl` and the three hand-grading tables).

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
- Repositories are keyed by the URL in the JOSS record; GitHub renames are not resolved.
- Only files that declare `cff-version: 1.2.0` are checked against the schema; JSON-schema
  `format` keywords are not enforced (the patterns are).
- Non-GitHub repositories (GitLab, Bitbucket and others) are counted and skipped.

## Licence

Apache-2.0 (see `LICENSE`). Text and data: CC BY 4.0.
