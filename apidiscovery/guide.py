"""Integration guidance for one API, in the project's language.

Grounded in what is known: the documentation link, the authentication kind, HTTPS and CORS as listed. The catalogue has
no endpoints, parameters, limits or prices, so the guide never states any: the example shows the shape of a correct
integration with the base address and path left as values to copy from the official documentation.

Rules the generated code keeps (tests/test_api_discovery.py checks every variant):
  * a credential is read from a server-side environment variable and is never in browser or mobile code, a URL logged
    to the console, or a variable a bundler exposes to the client (NEXT_PUBLIC_, VITE_, REACT_APP_, EXPO_PUBLIC_);
  * every call has a timeout, checks the status, handles 429, and its response is treated as data, never as markup;
  * nothing here signs up for an account, buys a plan or sends a project secret anywhere.

The catalogue's text (names, descriptions) is third-party content: it is used as inert data and never as instructions."""
import re

LANGS = {"javascript": "JavaScript (Node / serverless route)", "python": "Python", "curl": "curl"}
PUBLIC_PREFIX = ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "EXPO_PUBLIC_", "PUBLIC_", "NUXT_PUBLIC_", "GATSBY_")


def env_name(e):
    s = re.sub(r"[^A-Z0-9]+", "_", e["name"].upper()).strip("_") or "API"
    if s[0].isdigit(): s = "API_" + s
    return s[:40]


def label(e):
    """The API's name as it may appear inside generated code: letters, digits, spaces and . _ - only, so catalogue text
    can never close a string, open a template expression or start a comment."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ._-]", "", e["name"])).strip()[:60] or "the API"


def header_name(e):
    return re.sub(r"[^A-Za-z0-9-]", "", str(e.get("auth_raw") or ""))[:40] or "X-Api-Key"


def code_tokens(e):
    return {"label": label(e), "env": env_name(e), "pascal": _ident(e), "snake": _ident(e, snake=True), "header": header_name(e)}


def plan(e, platform="server"):
    """Where the call must run. A key never reaches a client; a keyless CORS API may be called from the browser."""
    secret = e["auth"] in ("apiKey", "oauth", "header", "unknown")
    direct = (not secret) and e["cors"] == "yes" and e["https"] == "yes" and platform in ("browser", "mobile")
    return {"secret": secret, "where": "client" if direct else "server",
            "why": ("No key is involved and the catalogue lists CORS and HTTPS, so the browser or app can call it directly." if direct else
                    "It needs a credential, so the call runs on your server and your client calls your server." if secret else
                    "No key is involved, but CORS or HTTPS is not listed as supported, so call it from your server." if platform != "server" else
                    "Call it from your server code.")}


def _env(e, T):
    n = T["env"]; out = [{"name": f"{n}_BASE_URL", "secret": False, "what": "the API's base address, copied from its documentation"}]
    if e["auth"] == "apiKey": out.append({"name": f"{n}_API_KEY", "secret": True, "what": "the key the provider issues when you sign up"})
    elif e["auth"] == "header": out.append({"name": f"{n}_API_KEY", "secret": True, "what": f"the value for the {T['header']} header"})
    elif e["auth"] == "oauth": out += [{"name": f"{n}_CLIENT_ID", "secret": False, "what": "your OAuth application's id"}, {"name": f"{n}_CLIENT_SECRET", "secret": True, "what": "your OAuth application's secret"}]
    elif e["auth"] == "unknown": out.append({"name": f"{n}_API_KEY", "secret": True, "what": "a credential, if its documentation requires one"})
    return out


def _js(e, P, T):
    n = T["env"]
    if P["where"] == "client":
        return (f"// Browser or app code. No credential is involved, so nothing here is secret.\n"
                f"const BASE_URL = \"https://<base address from the documentation>\";\n\n"
                f"export async function fetch{T['pascal']}(path, params = {{}}) {{\n"
                f"  const url = new URL(path, BASE_URL);\n  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));\n"
                f"  const res = await fetch(url, {{ signal: AbortSignal.timeout(8000) }});\n"
                f"  if (res.status === 429) throw new Error(\"Rate limited: wait before retrying\");\n"
                f"  if (!res.ok) throw new Error(`{T['label']} answered ${{res.status}}`);\n"
                f"  return res.json();   // data: validate it, and never insert it as HTML\n}}\n")
    hdr = {"apiKey": f"  // Send the key the way the documentation says (a header is safer than a query parameter, which ends up in logs).\n"
                     f"  const headers = {{ Authorization: `Bearer ${{process.env.{n}_API_KEY}}` }};\n",
           "header": f"  const headers = {{ \"{T['header']}\": process.env.{n}_API_KEY }};\n",
           "oauth": f"  const headers = {{ Authorization: `Bearer ${{await accessToken()}}` }};   // accessToken(): the provider's OAuth flow, tokens cached server-side\n",
           "unknown": f"  const headers = process.env.{n}_API_KEY ? {{ Authorization: `Bearer ${{process.env.{n}_API_KEY}}` }} : {{}};\n", "none": "  const headers = {};\n"}[e["auth"]]
    return (f"// Server code only (an API route, a serverless function, a backend). Never import this from browser or app code.\n"
            f"const BASE_URL = process.env.{n}_BASE_URL;   // from the official documentation\n"
            f"const cache = new Map();                     // replace with your platform's cache in production\n\n"
            f"export async function fetch{T['pascal']}(path, params = {{}}) {{\n"
            f"  const url = new URL(path, BASE_URL);\n  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));\n"
            f"  const hit = cache.get(url.href);\n  if (hit && hit.until > Date.now()) return hit.data;\n" + hdr +
            f"  const res = await fetch(url, {{ headers, signal: AbortSignal.timeout(8000) }});\n"
            f"  if (res.status === 429) throw new Error(\"Rate limited: back off (honour Retry-After)\");\n"
            f"  if (!res.ok) throw new Error(`{T['label']} answered ${{res.status}}`);   // do not log the URL or headers: they may hold the key\n"
            f"  const data = await res.json();               // data: validate the fields you use\n"
            f"  cache.set(url.href, {{ data, until: Date.now() + 5 * 60 * 1000 }});\n  return data;\n}}\n")


def _py(e, P, T):
    n = T["env"]
    hdr = {"apiKey": f"    headers = {{\"Authorization\": f\"Bearer {{os.environ['{n}_API_KEY']}}\"}}  # send it the way the documentation says\n",
           "header": f"    headers = {{\"{T['header']}\": os.environ[\"{n}_API_KEY\"]}}\n",
           "oauth": "    headers = {\"Authorization\": f\"Bearer {access_token()}\"}  # access_token(): the provider's OAuth flow, tokens cached server-side\n",
           "unknown": f"    key = os.environ.get(\"{n}_API_KEY\")\n    headers = {{\"Authorization\": f\"Bearer {{key}}\"}} if key else {{}}\n", "none": "    headers = {}\n"}[e["auth"]]
    return (f"# Server code. The credential comes from the environment and is never sent to a client.\n"
            f"import json, os, time, urllib.error, urllib.parse, urllib.request\n\n"
            f"BASE_URL = os.environ[\"{n}_BASE_URL\"]  # from the official documentation\n_cache = {{}}\n\n\n"
            f"def fetch_{T['snake']}(path, params=None, ttl=300):\n"
            f"    url = urllib.parse.urljoin(BASE_URL, path) + (\"?\" + urllib.parse.urlencode(params) if params else \"\")\n"
            f"    hit = _cache.get(url)\n    if hit and hit[0] > time.time():\n        return hit[1]\n" + hdr +
            f"    try:\n        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=8) as r:\n            data = json.load(r)  # data: validate the fields you use\n"
            f"    except urllib.error.HTTPError as e:\n        if e.code == 429:\n            raise RuntimeError(\"Rate limited: back off (honour Retry-After)\") from None\n"
            f"        raise RuntimeError(f\"{T['label']} answered {{e.code}}\") from None  # do not log the URL or headers: they may hold the key\n"
            f"    _cache[url] = (time.time() + ttl, data)\n    return data\n")


def _curl(e, P, T):
    n = T["env"]
    h = {"apiKey": f" -H \"Authorization: Bearer ${n}_API_KEY\"", "header": f" -H \"{T['header']}: ${n}_API_KEY\"", "oauth": " -H \"Authorization: Bearer $ACCESS_TOKEN\"", "unknown": "", "none": ""}[e["auth"]]
    return (f"# Run it from a terminal with the values exported, never pasted into a file you commit.\n"
            f"curl --fail-with-body --max-time 8{h} \\\n  \"${n}_BASE_URL/<path from the documentation>\"\n")


def _ident(e, snake=False):
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", e["name"]) if p] or ["Api"]
    s = "_".join(p.lower() for p in parts) if snake else "".join(p[:1].upper() + p[1:] for p in parts)
    return ("api_" if snake else "Api") + s if s[0].isdigit() else s


def guide(e, lang="javascript", platform="server", check=None, _tokens=None):
    """The integration guide for one entry: sections of plain text plus one code example. Nothing is fetched or run."""
    lang = lang if lang in LANGS else "javascript"
    platform = platform if platform in ("server", "browser", "mobile") else "server"
    P = plan(e, platform)
    if lang != "javascript" and P["where"] == "client":   # Python and curl examples are not browser or app code
        P = dict(P, where="server", why="No key is involved, so nothing here is secret. This example runs wherever you run it: a script, a server, a terminal.")
    T = _tokens or code_tokens(e)
    env = _env(e, T) if P["where"] == "server" else []
    code = {"javascript": _js, "python": _py, "curl": _curl}[lang](e, P, T)
    auth = {"none": "None listed. No sign-up is needed to make a request.",
            "apiKey": "An API key. Create an account with the provider yourself, generate a key, and store it as a server-side environment variable.",
            "oauth": "OAuth. Register an application with the provider yourself to get a client id and secret, then implement the flow its documentation describes.",
            "header": f"A request header ({T['header']}). Its documentation says what value to send.",
            "unknown": "Not stated in the catalogue. Its documentation says whether a credential is needed."}[e["auth"]]
    doc_note = None
    if check and check["status"] != "reachable":
        from .checks import STATUS
        doc_note = f"{STATUS.get(check['status'], check['status'])} when it was last checked ({str(check.get('checked'))[:10]})."
    sections = [
        {"title": "Official documentation", "body": [e["url"]] + ([doc_note] if doc_note else []) +
         ["Everything below is the shape of a sound integration. The addresses, parameters and limits are in that documentation, not in the catalogue."]},
        {"title": "Authentication", "body": ["As the catalogue lists it: " + auth[:1].lower() + auth[1:], P["why"]]},
        {"title": "Environment variables", "body": ([f"{v['name']}: {v['what']}" + (" (secret)" if v["secret"] else "") for v in env] +
                                                    ["Set them in your host's environment settings. Never give a secret a client-exposed prefix (NEXT_PUBLIC_, VITE_, REACT_APP_, EXPO_PUBLIC_) and never commit it."])
         if env else ["None needed: no credential is involved."]},
        {"title": "Endpoints", "body": ["The catalogue does not list endpoints. Take the base address and the paths you need from the official documentation; do not guess them."]},
        {"title": "Rate limits", "body": ["Not in the catalogue. Find the limits in its documentation or pricing page, handle HTTP 429 by waiting (honour Retry-After), and never retry in a tight loop."
                                          + (" Keyless APIs usually limit by IP address, which a server shared with other apps can exhaust quickly." if e["auth"] == "none" else "")]},
        {"title": "Error handling", "body": ["Set a timeout on every call, check the status before reading the body, and decide what your app shows when the API is slow, down or returns nothing: a third-party API will fail at some point."]},
        {"title": "Caching", "body": ["Cache responses for as long as the data stays useful (the example uses five minutes). It cuts latency, protects your quota and keeps the feature working through short outages. Check the provider's terms: some restrict caching."]},
        {"title": "Security", "body": [("Keep the credential on the server; the client talks to your server, never to the API with the key. " if P["secret"] else "") +
                                       "Validate inputs before forwarding them, treat responses as untrusted data (never insert them as HTML), and do not log full request URLs or headers."
                                       + (" It is listed as HTTP only: traffic is unencrypted, so do not send personal data or credentials to it." if e["https"] == "no" else "")]},
        {"title": "Before you ship", "body": ["Read its terms for commercial use, attribution and data retention. Creating an account or choosing a paid plan is your decision to make with the provider; this guide does neither."]},
    ]
    return {"api": {k: e.get(k) for k in ("id", "name", "category", "url", "auth", "https", "cors")}, "language": lang, "language_label": LANGS[lang], "platform": platform, "runs_on": P["where"],
            "sections": sections, "example": {"language": lang, "code": code}, "env": env,
            "grounding": "Built from the catalogue's fields (documentation link, authentication, HTTPS, CORS). No endpoint, limit or price is stated because none is known."}


def text(G):
    L = [f"# Integrating {G['api']['name']}", ""]
    for s in G["sections"]: L += [f"## {s['title']}", ""] + [f"- {b}" for b in s["body"]] + [""]
    return "\n".join(L + [f"## Example ({G['language_label']})", "", "```" + G["language"], G["example"]["code"].rstrip(), "```", "", f"_{G['grounding']}_"])
