# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Offline tests for census.py (no network)."""
import datetime
import unittest

try:  # the analysis tests need the job's two dependencies; helper tests need none
    import jsonschema
    import yaml  # noqa: F401
    HAVE_DEPS = True
except ImportError:  # pragma: no cover
    HAVE_DEPS = False

import census

MINI_SCHEMA = {
    "type": "object",
    "required": ["cff-version", "title"],
    "additionalProperties": False,
    "properties": {
        "cff-version": {"type": "string", "pattern": "^1\\.2\\.0$"},
        "title": {"type": "string"},
        "date-released": {"type": "string",
                          "pattern": "^[0-9]{4}-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])$"},
        "license": {"anyOf": [{"type": "string"},
                              {"type": "array", "items": {"type": "string"}}]},
        "doi": {"type": "string"},
        "identifiers": {"type": "array"},
        "preferred-citation": {"type": "object"},
    },
}


class TestHelpers(unittest.TestCase):
    def test_normalize_repo(self):
        self.assertEqual(census.normalize_repo("https://github.com/optiland/optiland"),
                         ("optiland", "optiland"))
        self.assertEqual(census.normalize_repo("https://github.com/a/b.git"), ("a", "b"))
        self.assertEqual(census.normalize_repo("http://www.github.com/A/B/tree/main/sub"),
                         ("A", "B"))
        self.assertEqual(census.normalize_repo("github.com/x/y"), ("x", "y"))
        self.assertEqual(census.normalize_repo("git@github.com:x/y.git"), ("x", "y"))
        self.assertIsNone(census.normalize_repo("https://gitlab.com/x/y"))
        self.assertIsNone(census.normalize_repo("https://github.com/onlyowner"))
        self.assertIsNone(census.normalize_repo(None))

    def test_repo_key_lowercase(self):
        self.assertEqual(census.repo_key(("A", "B")), "a/b")

    def test_joss_ids(self):
        self.assertEqual(census.joss_ids("10.21105/joss.01234"), {1234})
        self.assertEqual(census.joss_ids("https://doi.org/10.21105/JOSS.11170 and 10.21105/joss.00042"),
                         {11170, 42})
        self.assertEqual(census.joss_ids("10.5281/zenodo.123"), set())
        self.assertEqual(census.joss_ids(None), set())

    def test_stringify_dates(self):
        d = {"date-released": datetime.date(2020, 1, 2),
             "x": [datetime.datetime(2021, 3, 4, 5, 6)], True: 1}
        out = census.stringify_dates(d)
        self.assertEqual(out["date-released"], "2020-01-02")
        self.assertEqual(out["x"], ["2021-03-04"])
        self.assertIn("True", out)

    def test_core_doi_values(self):
        data = {"doi": "10.5281/zenodo.1",
                "identifiers": [{"type": "doi", "value": "10.5281/zenodo.2"},
                                {"type": "url", "value": "https://x"}],
                "preferred-citation": {"doi": "10.21105/joss.00001",
                                       "identifiers": [{"type": "DOI", "value": "10.1/abc"}]},
                "references": [{"doi": "10.21105/joss.00099"}]}
        vals = census.core_doi_values(data)
        self.assertIn(("doi", "10.5281/zenodo.1"), vals)
        self.assertIn(("identifiers", "10.5281/zenodo.2"), vals)
        self.assertIn(("preferred-citation.doi", "10.21105/joss.00001"), vals)
        self.assertIn(("preferred-citation.identifiers", "10.1/abc"), vals)
        self.assertEqual(len(vals), 4)  # references are not core
        self.assertEqual(census.core_doi_values(["not", "a", "dict"]), [])

    def test_classify_foreign(self):
        index = {5: {"repo_key": "a/b"}, 6: {"repo_key": "c/d"}}
        res = census.classify_foreign({5, 6, 7}, {5}, index, "a/b")
        self.assertEqual(res, [(6, "other_repo", "c/d"), (7, "not_published", "")])
        self.assertEqual(census.classify_foreign({5}, {5}, index, "a/b"), [])

    def test_placeholder(self):
        vals = [("doi", "10.5281/zenodo.XXXXXXX"), ("doi", "10.5281/zenodo.4242424"),
                ("preferred-citation.doi", "10.21105/joss.<number>")]
        self.assertEqual([v for _, v in census.placeholder_dois(vals)],
                         ["10.5281/zenodo.XXXXXXX", "10.21105/joss.<number>"])


@unittest.skipUnless(HAVE_DEPS, "pyyaml and jsonschema not installed")
class TestAnalyse(unittest.TestCase):
    def setUp(self):
        self.v = jsonschema.Draft7Validator(MINI_SCHEMA)

    def test_valid_with_yaml_date(self):
        text = "cff-version: 1.2.0\ntitle: T\ndate-released: 2020-01-02\nlicense: MIT\n"
        row, data = census.analyse_file(text, self.v)
        self.assertTrue(row["yaml_ok"])
        self.assertTrue(row["schema_checked"])
        self.assertTrue(row["schema_valid"], row["error_msgs"])
        self.assertFalse(row["license_is_list"])

    def test_invalid_extra_key_and_license_list(self):
        text = "cff-version: 1.2.0\ntitle: T\nlicense: [MIT, Apache-2.0]\nsubjects: x\n"
        row, _ = census.analyse_file(text, self.v)
        self.assertFalse(row["schema_valid"])
        self.assertIn("additionalProperties@<root>", row["error_classes"])
        self.assertTrue(row["license_is_list"])

    def test_missing_required(self):
        row, _ = census.analyse_file("cff-version: 1.2.0\n", self.v)
        self.assertFalse(row["schema_valid"])
        self.assertIn("required@<root>", row["error_classes"])

    def test_old_version_not_schema_checked(self):
        row, _ = census.analyse_file("cff-version: 1.1.0\ntitle: T\n", self.v)
        self.assertEqual(row["cff_version"], "1.1.0")
        self.assertFalse(row["schema_checked"])
        self.assertIsNone(row["schema_valid"])

    def test_yaml_error(self):
        row, data = census.analyse_file("cff-version: 1.2.0\ntitle: [unclosed\n", self.v)
        self.assertFalse(row["yaml_ok"])
        self.assertIsNone(data)

    def test_not_mapping(self):
        row, data = census.analyse_file("- a\n- b\n", self.v)
        self.assertTrue(row["yaml_ok"])
        self.assertFalse(row["is_mapping"])

    def test_nested_error_path_generalised(self):
        schema = {"type": "object", "properties": {"authors": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"name": {"type": "string"}}}}}}
        v = jsonschema.Draft7Validator(schema)
        text = "cff-version: 1.2.0\nauthors:\n  - name: A\n    email2: x\n"
        row, _ = census.analyse_file(text, v)
        self.assertIn("additionalProperties@authors/*", row["error_classes"])


if __name__ == "__main__":
    unittest.main()
