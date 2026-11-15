# API Discovery

Describe a need → discover APIs → compare what is known → inspect integration guidance.

A toolbox utility built on the [public-apis](https://github.com/public-apis/public-apis) catalogue. It is **not a
department**: it scores nothing, writes no provenance record, and never appears in a Production Report, a verdict or
any evaluator's rubric (`tests/test_api_discovery.py`, part 9).

## Where it is

| Surface | What |
|---|---|
| Live site | `/apis/` (linked as **APIs** in the site header): https://meshcraft-vert.vercel.app/apis/ |
| Claude Code (MCP, `studiocraft`) | `api_discovery_search`, `api_discovery_compare`, `api_discovery_guide`, `api_discovery_recommend`, `api_discovery_status` |
| Control room (`scripts/ui.sh`) | the same five tools, listed with every other `studiocraft` tool |
| Terminal | `python3 -m apidiscovery search "a free weather API for a mobile hiking app"` (also `compare`, `guide`, `recommend`, `status`, `refresh`, `check`) |

## What it will and will not tell you

Every statement carries its basis, and the three are never mixed:

| Basis | Meaning | Examples |
|---|---|---|
| **Catalogue (unverified)** | public-apis lists it so; nobody here checked | authentication, HTTPS, CORS, the description |
| **Checked** | measured by this tool, with the date | the documentation link answered / leads elsewhere / returned an error page / refused the check |
| **Unknown** | not in the catalogue and not measurable from outside; never guessed | pricing and free tier, rate limits, reliability and maintenance, licence and commercial use |

*Heuristic* marks advice derived from those (integration effort, "matches your words").

There are **no scores**. Results are ordered by how well the catalogue text matches the need, then by the constraints
in the sentence; the order is explained per result ("matched: weather in name") and is not a rating. "Free" is not in
the catalogue: a need that says "free" lists no-key APIs first and says that this is not the same thing.

A link check establishes one thing: on that date, from the checking machine, the documentation link answered. It is
not uptime, reliability or proof the API works, and a refusal (403, 429, a bot wall) is "refused the check", never "down".

## The catalogue

- **Source.** One Markdown file, `README.md` of public-apis (MIT, Copyright (c) 2022 public-apis). Its category tables
  give API, description, Auth, HTTPS and CORS. Its sponsor block, MCP-servers table and anything outside a category are
  not entries; tracking parameters are stripped from links and such listings are marked *sponsored*.
- **Normalised local index.** `apidiscovery/catalog.py` parses it into `apidiscovery/data/catalog.json` (committed):
  one entry per API (duplicates merged, the other categories kept in `also_in`), values outside the known vocabulary
  become `unknown`, every row that does not fit is listed in `skipped` with the reason. No search ever touches GitHub.
- **Independent facts are separate.** `apidiscovery/checks.py` writes `data/checks.json`; it never edits a catalogue field.
- **Refresh without a redeploy.** `.github/workflows/api-catalog.yml` (Mondays, or run it by hand) fetches the upstream,
  checks every documentation link once, and pushes `apis.json` to the `api-catalog` branch. The page loads the catalogue
  bundled with the deployment first, then adopts the published one only when it is valid and newer.
- **When the upstream is unavailable.** `refresh` keeps the working catalogue byte for byte and says why (unreachable,
  an error page, a truncated file). A check run in which most links are unreachable is treated as the checker's network
  and is not saved. A broken published file is ignored by the page. A missing catalogue makes the tools answer
  `unavailable` with the fix, and the site still builds.
- **Freshness is visible**: the page footer and every tool answer give the fetch date and the link-check date.
- **No database, no new service**: two JSON files in the repository and one data branch.

## Project-aware recommendations

`api_discovery_recommend {project}` reads the project read-only: `package.json` or a Python manifest (language,
platform), the README (needs), the Director's Discovery for the kind, and a bounded sample of source files for
hostnames (APIs it already seems to call). It never reads `.env` or other secret files, never adds a dependency, never
calls an API and writes nothing. A shared domain with a catalogue entry is reported as a lead, not as proof.

On the site there is no project to read, so the same context is two controls: **Building for** (server, browser, mobile
app) and **Examples in** (JavaScript, Python, curl). A need that names its platform sets the first one.

## Integration guidance

`api_discovery_guide {api, language?, platform?, project?}`: documentation, authentication, environment variables,
endpoints, rate limits, error handling, caching, security, and one example request.

- The catalogue has no endpoints, limits or prices, so the guide states none: the example shows the shape of a sound
  integration with the base address and paths to be copied from the official documentation.
- A credential is read from a server-side environment variable. It is never in browser or mobile code and never under a
  client-exposed name (`NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `EXPO_PUBLIC_`). Only a no-key API listed with CORS and
  HTTPS gets a client-side example.
- Catalogue text is third-party content. It reaches generated code only as letters, digits and `. _ -`, is shown on the
  page only as text, and is never treated as instructions.
- It creates no account, chooses no plan and sends no secret anywhere.

## Limits

- The catalogue is community-maintained: entries can be stale, renamed, paid, or gone. A listing is not an endorsement.
- Pricing, limits, reliability and licence terms are always unknown here. Only each provider's own pages answer them.
- Search matches the catalogue's one-line descriptions; it cannot know an API's actual endpoints.
- CORS is the catalogue's claim. Nothing here calls an API to test it.
- Deferred: verified pricing or free-tier data, real endpoint lists (OpenAPI), maintenance signals (changelogs, repository
  activity), and any reliability evaluation.
