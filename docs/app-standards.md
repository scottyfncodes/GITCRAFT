# App standards: App Icon Studio, HaveAnApp attribution, engineering quality

Every web app, site or game that GITCRAFT produces gets three standards. They aren't a checklist bolted on at the
end. The intake writes them into the spec, the Decision Room confirms them, the build work order asks for them, and
measured QA tasks (`qa.icons`, `qa.attribution`, `qa.standards`) gate the release like every other criterion.

Existing apps are not retrofitted. The standards apply to productions planned from now on. For an existing project
the Decision Room asks first (keep its icon? add the credit?).

| Standard | Spec field | Criterion | Measured by | Code |
|---|---|---|---|---|
| App icon | `icon {required, mode}` | `app_icon` | `icon.derivatives`, `qa.icons` | `production/icons.py` |
| HaveAnApp attribution | `attribution {required}` | `attribution` | `qa.attribution` | `production/standards.py`, `production/kit/haveanapp/` |
| Engineering | `engineering {profile, because}` | `engineering_standards` | `qa.standards` | `production/standards.py` |

## App Icon Studio

The icon is produced inside the production, with the tools GITCRAFT already has. There is no separate image
generator: VectorCraft and PhotoCraft draw it, and the Production Director measures, derives and verifies it.

1. **Discovery** inspects the project's icons (`icons.inspect`). Each one is classed as `none`, `generic` (a framework's
   default such as `vite.svg` or `logo192.png`), `weak` (too small or not square) or `candidate` (square and ≥ 512 px, or an SVG icon).
2. **Decision Room** asks for the icon direction (`app_icon`: new, refine or keep). Recommended: keep a candidate, otherwise a new icon.
3. **`icon.concepts`** (agent work order): 2–5 genuinely different concepts, each as a square PNG of ≥ 512 px with its SVG source, plus
   `concepts.json` with the idea behind each one and a recommendation. Each concept is in the app's own palette (from the identity),
   has one strong silhouette, and contains no tiny text, screenshots, framework imagery or HaveAnApp branding. There is no shared house style.
   The submission is validated: count, square, size, distinct files, unique ids, and a recommendation that names a concept.
4. **`icon.select`** (needs a person): writes `concepts.html`, which shows every concept side by side at full size and at 180, 64 and 32 px
   on light and dark backgrounds, with the recommendation marked. The production waits.
   - `production_approve {task: "icon.select", approved: true, choice: "<id>"}` records the choice in `selection.json`.
   - Declining with a note sends `icon.concepts` back with the feedback.
   - An icon is never chosen silently.
5. **`icon.master`** (agent): the approved concept, refined into a full-bleed 1024 × 1024 `icon-1024.png` and `icon.svg`.
   The master is validated at exactly 1024.
6. **`icon.derivatives`** (built-in, standard-library PNG/ICO codec):
   - Sizes: `icon-512.png`, `icon-192.png`, `icon-maskable-512.png`, `apple-touch-icon.png`, `favicon-32.png`, `favicon-16.png` and `favicon.ico`.
   - Opacity: the maskable icon puts the art in the 80% safe zone on the palette background. The Apple 180 icon is made opaque, because iOS fills transparency with black.
   - Snippet: `icons.snippet.json` holds the `<head>` tags and the manifest `icons`.
   - Small-size clarity is measured: at 32 px the icon must have a luminance spread ≥ 12, which is a proxy for "a shape is visible".
   - The set ships to `<asset_dir>/icons/` through the normal integration (hash-verified, with licence sidecars).
   - The master is kept as source artwork.
7. **Build**: the work order asks for the snippet to be wired in, merged into any existing manifest, and every old or framework icon reference removed.
8. **`qa.icons`** reads the built entry page and checks:
   - a favicon is linked;
   - the Apple touch icon is linked, exists, is 180 × 180 and is opaque;
   - a manifest is linked, names the app, and lists 192 and 512 icons (plus any maskable icon) that exist at those sizes;
   - no generic framework icon is used and no reference is broken;
   - small-size clarity;
   - a person approved the icon;
   - the linked files are byte-for-byte the approved derivatives.

**Base paths.** A static site gets relative URLs (`assets/icons/…`), which also work under a GitHub Pages subpath.
Files under `public/` get root-absolute URLs (`/icons/…`), and Vite or Next add the configured `base`.

**Not measured here:** whether the deployed URLs serve these files. That is part of the deployment evidence, a check that ran against the live URL.

## HaveAnApp attribution

The reference is HangarBook (read-only), which credits its maker as "HangarBook by HaveAnApp":
- the `Byline` component (`src/components/Brand.tsx`) sits beneath the wordmark on the launch and sign-in screens and in Settings → About;
- it is styled at 12 px, weight 500, letter-spacing 0.04em, in the muted text colour (`.byline` in `global.css`);
- the credit is also in the manifest description and `<meta name="author">`;
- the byline has no link.

The GITCRAFT standard (`production/kit/haveanapp/`):

- **`attribution.json`**: the company name, the byline text, the placements, the rules and the URL setting.
- **`byline.html`**: the plain markup, linked to https://haveanapp.com. It works in any framework.
- **`byline.css`**: small, medium weight and muted. It inherits the app's own text colour, so it follows light and dark themes without a palette of its own. It respects safe areas and keeps a 24 px touch target when linked.
- **`Byline.tsx`**: the React version.

**Placement:** in a footer, an About or Settings screen, under the app's name on a launch or title screen, or on a game's title or pause screen.
The app's name stays the hero; HaveAnApp is a quiet maker's signature, never an advertisement, and never inside the app icon.

**Link:** the byline links to the official site, **https://haveanapp.com** (confirmed by its owner; `attribution.json`).
HaveAnAppHQ is used only for Instagram posting and is never the byline's link. Every starter and every generated project
links it, and `qa.attribution` checks the link (a missing link, or any other address, fails).

**`qa.attribution`** checks that:
- the app's visible markup (HTML, JSX/TSX, Vue, Svelte, Astro; not `<meta>`, `<title>` or comments) has an element marked `data-haveanapp` that reads "by HaveAnApp";
- that element is not hidden;
- it links to https://haveanapp.com.

## Engineering standards (proportionate)

The intake picks a profile from what the idea says about who uses the app and what it holds. The Decision Room
shows the reason and lets the person change it:

| Profile | When | Adds |
|---|---|---|
| `personal` | a private tool or game for a few people (the default for apps and games) | the basics only: no accounts, servers or paid services unless the blueprint says so |
| `public` | anyone can open it, or it has accounts (the default for sites) | input validation, a visible error path, pinned dependencies, no wildcard CORS |
| `sensitive` | payments, health, financial or personal data | auth on every server route, rate limits, no tokens or personal data in `localStorage`, separate environments |

`qa.standards` measures each check from the project's files and reports one of these results:
- `ok` or `failed`: measured;
- `review`: the check applies but can't be decided from files, so it goes to the report as a review item and never counts as a pass;
- `n/a`.

Only checks the profile requires can fail the gate.

| Check | personal | public | sensitive |
|---|---|---|---|
| viewport, `<html lang>`, title | ✓ | ✓ | ✓ |
| no secrets in source or committed `.env` files | ✓ | ✓ | ✓ |
| HTTPS subresources | ✓ | ✓ | ✓ |
| no `*` / `latest` dependency ranges | ✓ | ✓ | ✓ |
| no SQL built by string interpolation (server code) | ✓ | ✓ | ✓ |
| lockfile | | ✓ | ✓ |
| global error handler or error boundary (review if missing) | | ✓ | ✓ |
| CORS not `*`; server input validation (review); database indexes (review) | | ✓ | ✓ |
| authorisation and rate limits (review); no secrets in `localStorage` | | | ✓ |

Mobile usability and accessibility are measured in the rendered app by PIXELCRAFT (axe-core, touch targets, safe areas).
Load and frame rate are measured by TestCraft. `qa.standards` doesn't repeat them.

## Starters

A new, empty web project starts from a starter (`production/kit/starters`) instead of an empty folder:
`static-app` (apps and sites, no framework), `canvas-game` (2D games) or `vite-react` (apps that asked for React; the
build installs and commits the lockfile). Each one already meets these standards: `lang`, viewport and title, a visible
error path, the HaveAnApp byline, the manifest and the icon links the App Icon Studio fills, 44 px targets, light and dark
tokens, reduced motion and a feature-check file. `foundation.scaffold` copies a starter only into an empty folder and
never over a file; an existing project never gets one.

## Feature checks

A new app or site proves each planned feature in a browser. The build writes `tests/gitcraft.features.json`, one entry
per feature: the steps a person takes, ending in what they see.

```json
{"features": [{"name": "add an item", "requirement": "a shopping list",
  "steps": [{"fill": "#item", "value": "Milk"}, {"click": "#add"}, {"expect": "#list li", "text": "Milk"}]}]}
```

Steps: `click` (a CSS selector, or `[x, y]` for games), `fill`, `press`, `type`, `wait`, `expect` (an element is visible,
optionally containing text) and `assert` (a JavaScript expression). `qa.features` runs every feature in Chromium through
TestCraft's scripted play, each on a fresh page. A feature with no observable outcome is refused, and a failing feature
becomes a fix work order like any other gate. Games are played by PLAYCRAFT instead; a game's feature file is optional.
An existing project's feature file, when it has one, runs as an advisory check.

## Backend and data

When the idea needs shared data (accounts, sync, a shared list, a leaderboard), the Decision Room asks where it lives.
The recommendation is **hosted Postgres + a small API**; the alternative is **on the device only** (no server, no sync).

- `backend.provision` is a work order that needs the person's approval (`infrastructure`, never pre-authorised). It
  uses the connected Neon account: one project, a `development` branch and production. Each connection string goes only
  into the hosting provider's environment variables and a git-ignored `.env`.
- Its record (`backend.json`) holds names only. A record containing a connection string, key or password is refused.
- The build reads `DATABASE_URL` from the environment and keeps the schema in the repository as migrations, with an index
  for every column a query filters or joins on. `qa.standards` checks the migrations, parameterised SQL, validation and
  auth, at the depth the engineering profile asks for.

## HaveAnApp Pulse (analytics)

Optional, chosen in the Decision Room: the anonymous, cookieless page counter HangarBook ships
(`<script defer src="https://haveanapp-pulse-collect.vercel.app/p.js" data-app="<app>">`). It is recommended for
public apps and sites and not for private ones. `qa.standards` checks it is on the entry page when chosen, and that no
analytics is on the page when it was not. `verify-live` checks the script answers on the deployed site.

## Native app icons

When the idea is a native iOS or Android app, the App Icon Studio also derives native sets from the same approved
master, into `native-icons/`:

- **iOS:** `ios/AppIcon.appiconset` with the single-size 1024 × 1024 icon (opaque: the App Store rejects transparency) and its `Contents.json`.
- **Android:** `android/res/mipmap-{mdpi…xxxhdpi}/ic_launcher.png` (48–192 px), an adaptive icon (foreground with the art in the
  66 dp safe zone, `mipmap-anydpi-v26/ic_launcher.xml`) and its background colour.

The folders are integrated as they are (Android rejects stray files in `res/`, so the licence record is one
`LICENSE.assets.json` at the set's root). GITCRAFT builds web apps; these sets are ready for a native wrapper or app project.

## Tests

- `tests/test_lifecycle.py` covers the codec, inspection, concept and master validation, derivatives, verification, attribution and the three profiles,
  plus a real app production: concepts → declined with feedback → new concepts → a person's choice → master → icon set → build → `qa.icons`,
  `qa.attribution` (a missing byline fails and is fixed) and `qa.standards` → delivered.
- `tests/test_gaps.py` covers starters, the deployment/backend/analytics/native decisions (and that approving applies them),
  the backend approval and secret check, feature checks in Chromium (pass, fail, no outcome, missing), native icon sets,
  GitHub issues in Discovery, and `verify-live` (this build passes; changed bytes, a login wall and plain http fail; a real
  Vercel URL behind deployment protection is reported as a login wall).
- `tests/acceptance_production.py` runs the same path inside the master-prompt game, with VectorCraft drawing the concepts and the master.
