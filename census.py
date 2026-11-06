# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""JOSS CITATION.cff census 1.

For every paper published in the Journal of Open Source Software (JOSS), read the
default-branch CITATION.cff of its GitHub repository and record:
  - presence, YAML parse failures, cff-version;
  - CFF 1.2.0 JSON-schema validity (the official schema, tag 1.2.0) and error classes;
  - a list under `license` (which Zenodo's GitHub integration currently rejects,
    zenodo/zenodo-rdm#1509), and whether a .zenodo.json overrides the CFF;
  - which JOSS DOIs the file names in its core DOI fields (doi, identifiers,
    preferred-citation), and whether any of them belongs to a different repository's
    JOSS paper or to no published JOSS paper at all.
No API keys. Sources: joss.theoj.org/papers/published.json, raw.githubusercontent.com.

Usage: python census.py --out-dir /out [--limit N]
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "joss-cff-census/1.0 (MV2, Munim, Inc.; mv2@munimtech.com)"
JOSS_URL = "https://joss.theoj.org/papers/published.json?page={page}"
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
SCHEMA_URL = ("https://raw.githubusercontent.com/citation-file-format/"
              "citation-file-format/1.2.0/schema.json")

JOSS_DOI_RE = re.compile(r"10\.21105/joss\.0*(\d{1,6})", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"(x{3,}|<[^>]*>|\.\.\.|1234567)", re.IGNORECASE)


# ---------------------------------------------------------------- pure helpers
def normalize_repo(url):
    """Return (owner, repo) for a github.com URL, else None."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if u.startswith("git@github.com:"):
        u = "https://github.com/" + u[len("git@github.com:"):]
    if "://" not in u:
        u = "https://" + u
    p = urllib.parse.urlparse(u)
    host = (p.hostname or "").lower()
    if host not in ("github.com", "www.github.com"):
        return None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return owner, repo


def repo_key(owner_repo):
    return (owner_repo[0] + "/" + owner_repo[1]).lower()


def joss_ids(text):
    """Set of integer JOSS paper numbers named by 10.21105/joss.NNNNN strings."""
    if not text:
        return set()
    return {int(m.group(1)) for m in JOSS_DOI_RE.finditer(str(text))}


def stringify_dates(obj):
    """YAML date/datetime objects -> ISO strings (the CFF schema asks for this)."""
    if isinstance(obj, dict):
        return {str(k) if not isinstance(k, str) else k: stringify_dates(v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [stringify_dates(v) for v in obj]
    if isinstance(obj, datetime.datetime):
        return obj.date().isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    return obj


def core_doi_values(data):
    """DOI strings in the core fields: doi, identifiers[type=doi],
    preferred-citation.doi, preferred-citation.identifiers[type=doi].
    Returns a list of (field, value)."""
    out = []
    if not isinstance(data, dict):
        return out

    def from_block(block, prefix):
        if not isinstance(block, dict):
            return
        d = block.get("doi")
        if d is not None:
            out.append((prefix + "doi", str(d)))
        ids = block.get("identifiers")
        if isinstance(ids, list):
            for it in ids:
                if isinstance(it, dict) and str(it.get("type", "")).lower() == "doi" \
                        and it.get("value") is not None:
                    out.append((prefix + "identifiers", str(it.get("value"))))

    from_block(data, "")
    from_block(data.get("preferred-citation"), "preferred-citation.")
    return out


def error_class(err):
    """Short class for a jsonschema error: '<validator>@<generalised path>'."""
    path = []
    for p in err.absolute_path:
        path.append("*" if isinstance(p, int) else str(p))
    return "%s@%s" % (err.validator, "/".join(path) if path else "<root>")


def classify_foreign(ids_in_core, own_ids, joss_index, own_key):
    """For JOSS ids in the core DOI fields that are not this repo's own papers,
    return a list of (id, kind, other_repo_key) where kind is
    'other_repo' (a published JOSS paper of a different repository),
    'same_repo_other_paper' (cannot happen if own_ids is complete; kept for safety),
    or 'not_published' (no published JOSS paper has that number)."""
    res = []
    for i in sorted(ids_in_core - own_ids):
        rec = joss_index.get(i)
        if rec is None:
            res.append((i, "not_published", ""))
        elif rec.get("repo_key") == own_key:
            res.append((i, "same_repo_other_paper", own_key))
        else:
            res.append((i, "other_repo", rec.get("repo_key") or rec.get("software_repository") or ""))
    return res


def placeholder_dois(values):
    return [(f, v) for f, v in values if PLACEHOLDER_RE.search(v)]


# ---------------------------------------------------------------- network
def http_get(url, tries=5, timeout=30):
    """Return (status, bytes). status 404 is definitive; -1 means failed."""
    delay = 5
    last = -1
    for _ in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code in (404, 410, 451):
                return e.code, b""
            if e.code == 429 or e.code >= 500 or e.code == 403:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return e.code, b""
        except Exception:  # timeouts, resets
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last if last != -1 else -1, b""


def fetch_joss(limit_pages=600):
    papers = []
    seen = set()
    for page in range(1, limit_pages + 1):
        st, body = http_get(JOSS_URL.format(page=page))
        if st == 404 and page > 1:
            break
        if st != 200:
            raise RuntimeError("JOSS page %d status %s" % (page, st))
        recs = json.loads(body.decode("utf-8"))
        if not recs:
            break
        new = [r for r in recs if r.get("doi") not in seen]
        if not new:
            break  # the API repeated a page: stop
        for r in new:
            seen.add(r.get("doi"))
        papers.extend(new)
        time.sleep(0.3)
    return papers


# ---------------------------------------------------------------- main
def analyse_file(text, schema_validator):
    """Analyse one CITATION.cff text. Returns a dict (no network)."""
    import yaml
    row = {"yaml_ok": False, "is_mapping": False, "cff_version": "",
           "schema_checked": False, "schema_valid": None, "n_errors": 0,
           "error_classes": [], "error_msgs": [], "license_is_list": False,
           "core_dois": [], "has_preferred_citation": False}
    try:
        data = yaml.safe_load(text)
        row["yaml_ok"] = True
    except Exception as e:  # yaml.YAMLError and friends
        row["error_msgs"] = ["YAML: " + str(e).replace("\n", " ")[:200]]
        return row, None
    if not isinstance(data, dict):
        return row, None
    row["is_mapping"] = True
    data = stringify_dates(data)
    row["cff_version"] = str(data.get("cff-version", ""))
    row["license_is_list"] = isinstance(data.get("license"), list)
    row["has_preferred_citation"] = isinstance(data.get("preferred-citation"), dict)
    row["core_dois"] = core_doi_values(data)
    if row["cff_version"] == "1.2.0" and schema_validator is not None:
        errs = list(schema_validator.iter_errors(data))
        row["schema_checked"] = True
        row["schema_valid"] = not errs
        row["n_errors"] = len(errs)
        row["error_classes"] = sorted({error_class(e) for e in errs})
        row["error_msgs"] = [(error_class(e) + ": " + e.message)[:240] for e in errs[:6]]
    return row, data


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--limit", type=int, default=0, help="only the first N repos (debug)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(a.out_dir, "cff"), exist_ok=True)
    t0 = time.time()

    import jsonschema
    st, sb = http_get(SCHEMA_URL)
    if st != 200:
        raise RuntimeError("schema fetch failed: %s" % st)
    schema = json.loads(sb.decode("utf-8"))
    schema_sha = hashlib.sha256(sb).hexdigest()
    validator = jsonschema.Draft7Validator(schema)

    papers = fetch_joss()
    with open(os.path.join(a.out_dir, "joss_papers.jsonl"), "w", encoding="utf-8") as f:
        for p in papers:
            f.write(json.dumps({k: p.get(k) for k in (
                "doi", "title", "software_repository", "software_archive",
                "published_at", "languages", "state")}, ensure_ascii=False) + "\n")

    joss_index = {}
    repos = collections.OrderedDict()
    non_github = 0
    for p in papers:
        ids = joss_ids(p.get("doi"))
        nr = normalize_repo(p.get("software_repository"))
        key = repo_key(nr) if nr else ""
        for i in ids:
            joss_index[i] = {"repo_key": key, "software_repository": p.get("software_repository"),
                             "title": p.get("title")}
        if not nr:
            non_github += 1
            continue
        r = repos.setdefault(key, {"owner": nr[0], "repo": nr[1], "own_ids": set(),
                                   "dois": [], "archives": []})
        r["own_ids"] |= ids
        r["dois"].append(p.get("doi") or "")
        r["archives"].append(p.get("software_archive") or "")

    keys = list(repos.keys())
    if a.limit:
        keys = keys[:a.limit]

    def get_cff(key):
        r = repos[key]
        st, body = http_get(RAW.format(owner=r["owner"], repo=r["repo"], path="CITATION.cff"))
        return key, st, body

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for key, st, body in ex.map(get_cff, keys):
            results[key] = (st, body)

    rows, foreign_rows, err_counter, err_files = [], [], collections.Counter(), collections.Counter()
    cffv = collections.Counter()
    status_counter = collections.Counter()
    zen_needed = []
    for key in keys:
        r = repos[key]
        st, body = results[key]
        status_counter[str(st)] += 1
        row = {"repo_key": key, "owner": r["owner"], "repo": r["repo"],
               "joss_dois": ";".join(r["dois"]), "http_status": st, "present": st == 200}
        if st == 200:
            raw_name = (r["owner"] + "__" + r["repo"]).replace("/", "_") + ".cff"
            with open(os.path.join(a.out_dir, "cff", raw_name), "wb") as f:
                f.write(body)
            text = body.decode("utf-8", errors="replace")
            info, data = analyse_file(text, validator)
            row.update({k: info[k] for k in ("yaml_ok", "is_mapping", "cff_version",
                                             "schema_checked", "schema_valid", "n_errors",
                                             "license_is_list", "has_preferred_citation")})
            row["error_classes"] = ";".join(info["error_classes"])
            row["error_msgs"] = " | ".join(info["error_msgs"])
            if info["yaml_ok"] and info["is_mapping"]:
                cffv[info["cff_version"] or "<missing>"] += 1
            for c in info["error_classes"]:
                err_files[c] += 1
            for c in info["error_classes"]:
                err_counter[c.split("@")[0]] += 1
            core_vals = info["core_dois"]
            ids_core = set()
            for _, v in core_vals:
                ids_core |= joss_ids(v)
            ids_any = joss_ids(text)
            row["own_joss_in_core"] = bool(ids_core & r["own_ids"])
            row["own_joss_anywhere"] = bool(ids_any & r["own_ids"])
            row["joss_ids_core"] = ";".join(str(i) for i in sorted(ids_core))
            ph = placeholder_dois(core_vals)
            row["placeholder_dois"] = ";".join("%s=%s" % fv for fv in ph)
            for i, kind, other in classify_foreign(ids_core, r["own_ids"], joss_index, key):
                fields = [f for f, v in core_vals if i in joss_ids(v)]
                foreign_rows.append({"repo_key": key, "own_joss_dois": ";".join(r["dois"]),
                                     "foreign_joss_id": i, "kind": kind, "other_repo": other,
                                     "fields": ";".join(sorted(set(fields))),
                                     "other_title": (joss_index.get(i) or {}).get("title", "")})
            row["n_foreign_core"] = sum(1 for x in foreign_rows if x["repo_key"] == key)
            if info["license_is_list"]:
                zen_needed.append(key)
        rows.append(row)

    zen = {}
    for key in zen_needed:
        r = repos[key]
        st, _ = http_get(RAW.format(owner=r["owner"], repo=r["repo"], path=".zenodo.json"))
        zen[key] = st
    for row in rows:
        if row["repo_key"] in zen:
            row["zenodo_json_status"] = zen[row["repo_key"]]

    fields = ["repo_key", "owner", "repo", "joss_dois", "http_status", "present", "yaml_ok",
              "is_mapping", "cff_version", "schema_checked", "schema_valid", "n_errors",
              "error_classes", "error_msgs", "license_is_list", "zenodo_json_status",
              "has_preferred_citation", "own_joss_in_core", "own_joss_anywhere",
              "joss_ids_core", "n_foreign_core", "placeholder_dois"]
    with open(os.path.join(a.out_dir, "repos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    with open(os.path.join(a.out_dir, "foreign.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["repo_key", "own_joss_dois", "foreign_joss_id", "kind",
                                          "other_repo", "fields", "other_title"])
        w.writeheader()
        for fr in foreign_rows:
            w.writerow(fr)

    present = [r for r in rows if r["present"]]
    parsed = [r for r in present if r.get("yaml_ok") and r.get("is_mapping")]
    checked = [r for r in present if r.get("schema_checked")]
    invalid = [r for r in checked if r.get("schema_valid") is False]

    # P8 grading sample: the 30 invalid files with the lowest sha256(repo_key)
    sample = sorted(invalid, key=lambda r: hashlib.sha256(r["repo_key"].encode("utf-8")).hexdigest())[:30]
    with open(os.path.join(a.out_dir, "sample_invalid.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["repo_key", "error_classes", "error_msgs"],
                           extrasaction="ignore")
        w.writeheader()
        for r in sample:
            w.writerow(r)
    lic_list = [r for r in present if r.get("license_is_list")]
    lic_list_no_zen = [r for r in lic_list if r.get("zenodo_json_status") == 404]
    definitive = sum(1 for r in rows if r["http_status"] in (200, 404))
    summary = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_s": round(time.time() - t0, 1),
        "schema_url": SCHEMA_URL, "schema_sha256": schema_sha,
        "jsonschema_version": getattr(jsonschema, "__version__", ""),
        "joss_papers": len(papers),
        "joss_papers_non_github": non_github,
        "distinct_github_repos": len(repos),
        "repos_scanned": len(keys),
        "http_status_counts": dict(status_counter),
        "definitive_fetch_share": round(definitive / max(1, len(keys)), 4),
        "cff_present": len(present),
        "cff_present_share": round(len(present) / max(1, definitive), 4),
        "yaml_fail": sum(1 for r in present if not r.get("yaml_ok")),
        "not_mapping": sum(1 for r in present if r.get("yaml_ok") and not r.get("is_mapping")),
        "cff_version_counts": dict(cffv.most_common()),
        "non_120_share_of_parsed": round(sum(v for k, v in cffv.items() if k != "1.2.0")
                                         / max(1, len(parsed)), 4),
        "schema_checked": len(checked),
        "schema_invalid": len(invalid),
        "schema_invalid_share": round(len(invalid) / max(1, len(checked)), 4),
        "error_validator_files": dict(collections.Counter(
            v for r in invalid for v in {c.split("@")[0] for c in r["error_classes"].split(";") if c}
        ).most_common()),
        "error_class_files_top30": dict(err_files.most_common(30)),
        "license_list": len(lic_list),
        "license_list_share_of_parsed": round(len(lic_list) / max(1, len(parsed)), 4),
        "license_list_without_zenodo_json": len(lic_list_no_zen),
        "license_list_zenodo_status": dict(collections.Counter(
            str(r.get("zenodo_json_status")) for r in lic_list)),
        "has_preferred_citation": sum(1 for r in parsed if r.get("has_preferred_citation")),
        "own_joss_in_core": sum(1 for r in parsed if r.get("own_joss_in_core")),
        "own_joss_anywhere": sum(1 for r in parsed if r.get("own_joss_anywhere")),
        "own_joss_anywhere_share_of_parsed": round(
            sum(1 for r in parsed if r.get("own_joss_anywhere")) / max(1, len(parsed)), 4),
        "foreign_core_rows": len(foreign_rows),
        "foreign_core_repos": len({x["repo_key"] for x in foreign_rows}),
        "foreign_kind_counts": dict(collections.Counter(x["kind"] for x in foreign_rows)),
        "placeholder_doi_repos": sum(1 for r in present if r.get("placeholder_dois")),
    }
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, sort_keys=False)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
