# Grading: JOSS CITATION.cff census 1

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-06 against `PREREG.md` (committed before
any output was read). Made with AI agents working in MV2's name; the grading was done by those
agents reading the raw files, not by a human. Text and data CC BY 4.0.

**Result: the gate passed and 5 of 8 predictions held (P1, P2, P4, P7, P8). P3, P5 and P6
failed.** P6 failed in an instructive way: every "foreign" JOSS DOI turned out to be a project
that moved to a new GitHub organisation and now asks to be cited by its newer JOSS paper.

The census ran once (job `joss-cff-census1-v1`, 2026-11-06 13:59-14:02 UTC, 215 s, all 14
unit tests passed). Outputs are in `results/census1/`.

## Gate (passed)

| Check | Needed | Got |
|---|---|---|
| JOSS papers | >= 3,000 | 3,787 (192 on non-GitHub hosts, skipped) |
| Distinct GitHub repositories | >= 2,800 | 3,573 |
| Definitive fetches (200 or 404) | >= 97% | 100% (1,192 x 200, 2,381 x 404) |
| CFF files | >= 600 | 1,192 |

## Predictions

| # | Prediction | Result | Held? |
|---|---|---|---|
| P1 | 25-50% of repositories have a CITATION.cff | 1,192 / 3,573 = **33.4%** (lower bound: a 404 can also be a deleted repo) | yes |
| P2 | >= 10% of cff-version 1.2.0 files fail the schema | 125 / 1,097 = **11.4%** | yes |
| P3 | `additionalProperties` is the most common failing validator (per file) | anyOf 36, required 35, type 27, **additionalProperties 27** | **no** |
| P4 | list `license` in 0.3-5% of parsed files, and >= half without `.zenodo.json` | 4 / 1,178 = **0.34%**; 2 of 4 have no `.zenodo.json` (exactly half) | yes (both at the edge) |
| P5 | 40-80% of parsed files name the repository's own JOSS DOI | 952 / 1,178 = **80.8%** | **no** (just above) |
| P6 | >= 3 repositories name a foreign JOSS DOI in a core field, and >= half of `other_repo` cases are errors | 3 repositories; **0 of 3** are errors | **no** |
| P7 | <= 10% of parsed files declare a cff-version other than 1.2.0 | 81 / 1,178 = **6.9%** | yes |
| P8 | >= 27 of 30 sampled invalid files have their first error confirmed in the raw file | **30 / 30** | yes |

Parsed files = 1,192 present - 14 YAML failures = 1,178 (no file parsed to a non-mapping).

### P3: why anyOf, not additionalProperties

`anyOf@authors/*` (26 files) and `anyOf@preferred-citation/authors/*` (10) mean an author entry
matches neither a CFF person nor a CFF entity. In the hand-graded sample the causes were: a bare
ORCID iD (`0000-0002-...` where the schema requires `https://orcid.org/0000-0002-...`; at
least 16 of the 125 invalid files, counted from the recorded error messages, which are
truncated, so this is a lower bound), a key CFF does not have (`middle-names`, a misspelt
`oricd`), and a malformed iD. Root `additionalProperties` (23 files) is common but third.

### P5: 80.8%

More files name their own JOSS DOI than predicted: 937 in a core field and 952 anywhere. 894
files have a `preferred-citation`. JOSS repositories cite their own paper more often than the
prediction assumed.

### P6: the "foreign" DOIs are moved repositories (instrument limitation)

| Old repository (JOSS record) | DOI named in `preferred-citation` | Belongs to |
|---|---|---|
| mackelab/sbi (joss.02505, 2020) | joss.07754 "sbi reloaded" (2025) | sbi-dev/sbi |
| cosmo-epfl/chemiscope (joss.02117, 2020) | joss.10380 "Chemiscope 1.0" (2026) | lab-cosmo/chemiscope |
| dib-lab/sourmash (joss.00027, 2016) | joss.06830 "sourmash v4" (2024) | sourmash-bio/sourmash |

In each case the census fetched a file through the old path (GitHub serves renamed
repositories there; re-read live for sbi on 2026-11-06), and the project deliberately asks to
be cited by its newer paper. None is an error. The census grouped repositories by the
URL string in the JOSS record and did not resolve GitHub renames, so a moved project with two
JOSS papers shows up as two "repositories" that share one file. **Consequence:** the 3,573
repositories include some duplicates of this kind, and any follow-up must resolve renames
first (the archive-DOI audit already does).

## Hand checks (all in `results/census1/`)

- `grade_sample_invalid.csv`: the 30 pre-registered files (lowest sha256 of repo key), with the
  line in the raw file that causes the first error. All 30 confirmed against the 1.2.0 schema
  (`schema.json` sha256 `0b8d2214...`).
- `grade_license_list.csv`: all 4 list-license files. The two without `.zenodo.json`
  (tum-esm/ivy, IslasGECI/nerd) were re-read live on 2026-11-06 and are unchanged. Both also
  use lower-case IDs (`cc-by-4.0`, `agpl-3.0-only`) that the CFF enum rejects on their own.
  Whether Zenodo would reject them depends on the projects using Zenodo's GitHub integration.
  That was not checked.
- `grade_foreign.csv`: the 3 `other_repo` cases (above). There were no `not_published` cases.
- Owner rule: no owner holds more than 5% of any count. The largest owner among invalid files
  holds 2 of 125. Among all repositories, rOpenSci holds 84 of 3,573 (2.4%).

## Descriptive findings (no prediction)

- **JOSS's own BibTeX leaks into CFF:** 17 of the 125 invalid files give
  `preferred-citation.publisher` as the plain string `"The Open Journal"`. CFF needs an object
  (`publisher: {name: The Open Journal}`). That is how JOSS's BibTeX writes it, so the error
  is probably hand-copied. In all, 21 files fail on the type of `preferred-citation.publisher`.
- **Citation-only files:** some files hold only `cff-version` and a `preferred-citation`
  (for example regional-mom6, eigentools and GeophysicalFlows.jl), so they lack top-level
  `authors`, `title` and `message`. 27 files fail `required` at the root; in 14 of them the
  recorded messages show that top-level `authors` is missing.
- **DOI written as a URL** (`https://doi.org/10...`, `doi.org/10...`): 9 files.
- **cff-version that has no CFF release** (the latest is 1.2.0): 20 files, for example 1.3.0
  (3), 2.0.0 (2), 1.27.1, 3.4.1 and v1.0.0. These look like the software's own version written
  in the wrong field. One file has no cff-version.
- **Placeholder and stale DOIs:** EdwardBerman/shopt has `doi: 10.5281/zenodo.1234567` with a
  comment to replace it, and DataCite has no record of that DOI (404, 2026-11-06). CNES/lenapy's
  `preferred-citation` still says `doi: "(submitted)"` with volume `xx`, although the paper is
  published as 10.21105/joss.09189.
- 14 files are not valid YAML.

## Prior art, re-checked at grading

A new search (2026-11-06) found no JOSS-wide schema-validity count. The nearest is still Shan,
arXiv:2608.17159: 10 of its 15 JOSS projects had a CITATION.cff, a small and likely
better-maintained sample, against 33.4% across all 3,573 repositories here. Single-repository
fix issues are common, but none reports a rate.

## Limits

- Default branch only, at one moment (2026-11-06 ~14:00 UTC). Files change.
- Presence is a lower bound (a 404 is also returned for deleted or private repositories) and
  repositories were not de-duplicated across GitHub renames (see P6).
- Error-message counts above come from truncated messages and are lower bounds. Validator
  counts (P3) come from the untruncated per-file classes.
- Schema validity is not the same as breakage: GitHub's "Cite this repository" and Zenodo
  tolerate some invalid files. This census measures conformance to the published schema only.

## What happens next

No issues are being filed on the repositories above. The archive-DOI audit
(`munimtechnologies/joss-archive-doi-audit`) is pre-registered and waiting for compute. A
follow-up count of the `"The Open Journal"` publisher string and the bare-ORCID pattern would
need its own pre-registration on a fresh sample.
