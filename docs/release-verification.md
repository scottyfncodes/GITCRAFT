# Release verification

GITCRAFT must tell a **broken application** apart from a **broken or incomplete verification**, without lowering the bar.
Code: `production/verification.py` (categories, release summary), `production/live.py` (`verify-live`),
`studio/core/netclass.py` (network and console classification), `production/standards.py` (engineering checks).
Regression suite: `tests/test_release_verification.py` (POW NOW PR #40).

## Four categories

| Category | Means | Effect |
|---|---|---|
| **BLOCKER** | a confirmed application failure, security vulnerability, broken functionality, or a violated mandatory requirement | NOT READY |
| **UNVERIFIED** | the check could not be completed: the verifier's network was restricted, an external service was down, a runtime was missing, or the evidence is insufficient | never READY; never reported as an app failure |
| **ADVISORY** | a non-blocking improvement, a configuration-metadata mismatch, or an accepted architectural decision | shown; never blocks |
| **PASS** | verified with appropriate evidence | — |

A check without a category is PASS when it passed and BLOCKER when it did not: nothing is downgraded without saying why.

Deployment status, verification completeness and release readiness are reported separately. The release status line:

- **READY**: every mandatory check passed with evidence (and the deployment, when there is one, verified).
- **NOT READY**: at least one BLOCKER.
- **DEPLOYED · VERIFICATION INCOMPLETE**: the URL serves this release, no BLOCKER, mandatory checks unverified.
- **VERIFICATION INCOMPLETE**: no BLOCKER, mandatory checks unverified, not (verifiably) deployed.

The production verdict stays READY / NOT READY / INCOMPLETE; the release status line adds the deployment.

## This release: provenance, not file names

Bundlers name files by content hash, and two build machines can produce different bundles for the same commit. A
hashed name that differs between the local build and Vercel's is never a failure by itself. Evidence, strongest first:

1. The deployment's commit (`verify-live --commit <sha>`, e.g. Vercel's `githubCommitSha`, or a `<meta name="commit">`
   tag in the live page) equals the project's HEAD: PASS. A different commit: BLOCKER (older deployment).
2. The live entry page equals the released one once content-hashed names, build-id segments, `nonce` and `integrity`
   are masked: PASS.
3. It differs and nothing proves which commit is live: UNVERIFIED (`no_provenance`). A different `<title>` or a login wall: BLOCKER.

Then every same-origin file the **live** page references must load (200, not empty), or it is a BLOCKER. Files with
stable names that the release ships verbatim (`public/`, or an unbuilt site) must be byte-identical; stable-named
build outputs are compared only as an advisory once the release is proven.

## External services and restricted networks

`netclass.classify_request` separates:

| What happened | Cause | Category |
|---|---|---|
| the proxy refused it, DNS failed, the tunnel failed, the harness blocked it | `sandbox_network` | UNVERIFIED |
| the external host answered 5xx or 429 | `external_service` | UNVERIFIED |
| no answer and no network explanation | `no_answer` | UNVERIFIED |
| the app's own origin failed, or an external host answered 4xx (not 401/403/407/429) | `application` | BLOCKER |

Whether the app stayed usable while the service was unreachable is a separate PASS (resilience). It is never presented as
proof that the live integration works, and neither is a mocked response. An UNVERIFIED sandbox check is resolved only by
independent production evidence: a live check, run with network against this release, that reached every host the sandbox
could not (`hosts_ok` in `live-check.json`).

## Smoke-test console policy

TestCraft's smoke test never ignores console errors globally:

- an error the browser raised for a request the harness blocked is explained, and each blocked host the app depends on
  (fetch, XHR, script, socket) becomes an UNVERIFIED check; fonts, styles and images from a CDN are an ADVISORY;
- an error matched by a documented exception, `console_error_exceptions: [{pattern, reason, host?}]`, is listed with its
  reason. The pattern must not match every message, the reason is required, and with `host` it applies only in a run where
  that host was unreachable. In a production, `spec.verification.console_error_exceptions` does the same for `verify-live`;
- anything else fails the check (the deprecated `allow_console_errors` turns it into a listed ADVISORY, never a silent pass);
- page exceptions and missing files are separate checks and are never excepted.

## Engineering advisories

- **Public read-only APIs**: wildcard CORS on GET-only routes without credentials is an ADVISORY, which still names abuse
  exposure (an upstream proxied without caching or a rate limit). Wildcard CORS on write routes or with credentials/cookies
  fails, and so does a route that returns `process.env`, whatever the profile.
- **Analytics**: Discovery (`maturity.assess`, `intake`) recognises the analytics a project already ships, and an existing
  project's spec declares them (`source: discovered`). Analytics nobody decided on are an ADVISORY. When the Decision Room chose
  none, Pulse on the page still fails. A Pulse tag without `data-app` is a metadata ADVISORY. A declared Pulse missing from the
  page is a failure.
- **Accepted decisions**: `.gitcraft/accepted.json` in the project (`[{check, fingerprint, reason, by?}]`, written by a person,
  read-only to GITCRAFT) keeps an advisory or review item from being raised again while its evidence fingerprint is unchanged.
  Failed checks can never be accepted.

## Gates and the engine

A gate whose only failing checks are UNVERIFIED reports `category: unverified`. The engine records the task as `blocked`
with `unverified: [...]` and the reason "verification incomplete (not an application failure)", and writes no fix work order.
The criterion reads `unverified` and the verdict reads INCOMPLETE. A criterion measured only by advisory tasks is `advisory`
and counts as passing.
