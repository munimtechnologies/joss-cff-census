# Pre-registration: JOSS CITATION.cff census 1

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-06, before any census output was read.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text
and data CC BY 4.0.

## Question

Papers in the Journal of Open Source Software (JOSS) point to a software repository. Many of
those repositories carry a `CITATION.cff` file, which GitHub turns into its "Cite this
repository" box and which Zenodo's GitHub integration reads when it archives a release.
Across **every** published JOSS paper:

1. How many repositories have a `CITATION.cff` on their default branch?
2. How many of the files that declare `cff-version: 1.2.0` fail the official CFF 1.2.0 JSON
   schema, and with which errors?
3. How many use a **list** under `license`? The CFF schema allows that, but Zenodo's GitHub
   integration currently rejects it with "Citation metadata load failed" and mints no DOI
   ([zenodo/zenodo-rdm#1509](https://github.com/zenodo/zenodo-rdm/issues/1509), open,
   2026-11-01). Zenodo uses `.zenodo.json` instead of the CFF when both exist, so the census
   also checks for `.zenodo.json` in those repositories.
4. Does the file name the repository's own JOSS paper DOI anywhere? Does a core DOI field
   (`doi`, `identifiers`, `preferred-citation.doi`, `preferred-citation.identifiers`) name a
   JOSS DOI that belongs to **another** repository's paper, or to no published JOSS paper at all?

## Nearest prior work and the delta

- Shan, *Does Research Software Agree with Itself? A Multi-Surface Consistency Audit of
  Software Citation Metadata*, arXiv:2608.17159 (Aug 2026): 117 projects (15 from JOSS),
  compares title/authors/version/year/DOI/license across CFF, codemeta, .zenodo.json, DOI
  records, PyPI/npm and README. It does **not** check schema validity, Zenodo's license-list
  rejection, or whether a JOSS DOI in the file belongs to a different paper. Its JOSS stratum
  is 15 projects; this census reads every JOSS repository on GitHub.
- RSMetacheck (SoftwareUnderstanding/rsmetacheck): a bot that flags metadata pitfalls,
  mostly in codemeta.json and package files, on about 1,500 repositories; no JOSS-wide CFF
  validity rate is published.
- OpenDORS (Druskat & Grunske, arXiv:2512.01570) records whether metadata files exist in
  about 122K research-software repositories, but not whether they are valid.
- RSE18 Hack Day (Software Sustainability Institute, 2018): an informal JOSS check found
  14 citation files, 2 of them CFF.
- pubroot-website#301 (2026-11-05) tests CFF converters on 38 synthetic files and asks for
  a real-world sample.
- Many single-repository issues and PRs fix one CFF file at a time. None gives a rate.

No published JOSS-wide count of CFF schema validity, license lists or foreign JOSS DOIs was
found (searches on 2026-11-06: "CITATION.cff empirical study", "CITATION.cff adoption JOSS",
"percentage of CITATION.cff files invalid", "CITATION.cff wrong JOSS DOI").

## Method (fixed by `census.py` in this commit)

- Paper list: `https://joss.theoj.org/papers/published.json?page=N` until an empty page.
- Repository: `software_repository` parsed to `owner/repo` (github.com only; other hosts are
  counted and skipped). Papers sharing a repository are grouped, and the repository's own JOSS
  DOIs are the DOIs of all of them.
- File: `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/CITATION.cff` (default
  branch). 404 counts as absent: it cannot tell a deleted repository from a missing file, so
  presence is a lower bound.
- Parsing: PyYAML `safe_load`. YAML dates become ISO strings before validation, as the schema
  asks.
- Schema: the official `schema.json` at tag `1.2.0` of citation-file-format/citation-file-format
  (sha256 recorded), with jsonschema `Draft7Validator`. `format` keywords are not enforced; the
  patterns are. Only files that declare `cff-version: 1.2.0` are validated. Other versions are
  counted separately.
- Error classes: `<validator>@<path>`, with list indices replaced by `*`.
- `.zenodo.json` is fetched only for files with a list under `license`.
- Placeholder DOIs: a core DOI value containing `xxx`, `<...>`, `...` or `1234567`.

## Predictions (blind: only three CFF files and one page of the paper list were read beforehand)

- **G (gate):** at least 3,000 JOSS papers; at least 2,800 distinct GitHub repositories; at
  least 97% of fetches definitive (200 or 404); at least 600 CFF files. If the gate fails,
  nothing below is graded.
- **P1:** between 25% and 50% of repositories have a CITATION.cff.
- **P2:** at least 10% of files that declare cff-version 1.2.0 fail the schema.
- **P3:** among failing files, `additionalProperties` is the most common validator (counted
  once per file).
- **P4:** list-valued `license` is in 0.3% to 5% of parsed files, and at least half of those
  repositories have no `.zenodo.json` (404).
- **P5:** between 40% and 80% of parsed files name the repository's own JOSS DOI anywhere.
- **P6:** at least 3 repositories name a foreign JOSS DOI in a core field, and on hand-grading
  at least half of the `other_repo` cases are errors, not deliberate choices (for example a
  moved repository, or a sibling package whose paper is the intended citation).
- **P7:** at most 10% of parsed files declare a cff-version other than 1.2.0.
- **P8 (instrument):** of 30 schema-invalid files, picked as the 30 with the lowest
  sha256(repo_key), at least 27 have their first listed error confirmed by reading the raw
  file against the schema.

Descriptive only (no prediction): YAML failures, non-mapping files, placeholder DOIs, how many
files have `preferred-citation`, and the most common error classes.

## Grading plan

Grading will be done by hand, from `summary.json`, `repos.csv`, `foreign.csv` and the saved raw
files. Every `other_repo` and `not_published` foreign case, and every list-license file without
`.zenodo.json`, will be checked against the live raw file. Results will be reported with and
without the single largest owner (by number of repositories) if one owner holds more than 5%
of any count.

## What will not be done

Nothing will be filed upstream (no issues, PRs or comments on the repositories found) before
grading. After grading, at most one summary write-up. Single reports only for clear,
hand-confirmed foreign-DOI errors, paced and disclosed as made with AI agents.
