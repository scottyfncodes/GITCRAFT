"""API Discovery: find, compare and integrate external APIs, grounded in the public-apis catalogue.

A toolbox utility, not a department: it scores nothing, writes no .studio.json record, and never appears in a
Production Report (tests/test_api_discovery.py holds that). Standard library only.

  catalog.py   the public-apis README → a normalised local catalogue (data/catalog.json), refreshed with a fallback
  checks.py    independent link checks (data/checks.json), kept apart from what the catalogue claims
  search.py    a described need → ranked candidates, with the reasons and the filters that were applied
  intel.py     what is known about a candidate, criterion by criterion, each statement with its basis
  guide.py     integration guidance for one API in the project's language (keys stay on the server)
  project.py   read-only project context: language, platform, needs, APIs already in use
  site.py      the static /apis/ page and its data file

Three kinds of statement, never mixed: `catalogue` (public-apis says so; nobody here verified it), `checked` (this
tool measured it, on the date shown) and `unknown` (pricing, rate limits, licence terms, reliability: not in the
catalogue and not measurable from outside). `heuristic` marks advice derived from the other three."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
VERSION = "1.0.0"
UPSTREAM = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
SOURCE = {"name": "public-apis", "url": "https://github.com/public-apis/public-apis", "license": "MIT", "copyright": "Copyright (c) 2022 public-apis",
          "note": "The list of APIs, their descriptions and the Auth / HTTPS / CORS columns come from the public-apis project (MIT). "
                  "GITCRAFT normalised them and added nothing to those columns."}
