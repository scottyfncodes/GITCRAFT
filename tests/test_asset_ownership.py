#!/usr/bin/env python3
"""AssetCraft licence report: first-party (project-owned) artwork vs restricted third-party assets.

A project's own artwork may be proprietary (all rights reserved by its owner) and is cleared to ship; a third-party
asset under proprietary, non-commercial or no-derivatives terms stays restricted. Ownership is declared, never
inferred: by `"first_party": true` in the asset's licence record, or the LicenseRef-Project-Owned id.

    python3 tests/test_asset_ownership.py
"""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(prefix="gc-ownership-")
os.environ["GITCRAFT_ASSET_CATALOG"] = os.path.join(tmp, "catalog.sqlite")
os.environ.setdefault("GITCRAFT_HOME", os.path.join(tmp, "home"))
sys.path.insert(0, os.path.join(ROOT, "studio"))
from core import catalog as C  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    fails += 0 if ok else 1


SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#{}"/></svg>'


def project(name):
    p = os.path.join(tmp, name)
    os.makedirs(os.path.join(p, ".git"), exist_ok=True)
    return p


def asset(proj, rel, colour="c29d5f"):
    path = os.path.join(proj, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(SVG.format(colour))
    return path


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w"))


# 1. The case that failed in production: a web game's own icons, recorded as proprietary, shipped from public/.
game = project("game")
icon = asset(game, "public/icon.svg")
og = asset(game, "public/og.svg", "201a14")
for p in (icon, og):   # catalogued first, as an earlier scan or registration left them: proprietary, no ownership flag
    C.register(p, license="LicenseRef-Proprietary", source={"type": "manual", "note": "original artwork"}, project=game)
rep = C.license_report(game)
check("an undeclared proprietary asset is restricted (ownership is never inferred)", "LicenseRef-Proprietary" in rep["restricted"], rep)

write(os.path.join(game, "LICENSE.assets.json"),
      {"public/icon*.svg": {"license": "LicenseRef-Proprietary", "first_party": True, "owner": "HaveAnApp"},
       "public/og.svg": {"license": "LicenseRef-Proprietary", "first_party": True, "owner": "HaveAnApp"}})
rep = C.license_report(game)
check("first-party proprietary artwork declared at the project root is not restricted", rep["restricted"] == {}, rep)
check("it is listed as the project's own, licence unchanged", sorted(rep["first_party"].get("LicenseRef-Proprietary", [])) == ["public/icon.svg", "public/og.svg"], rep)
check("its licence stays proprietary in the inventory", rep["by_license"] == {"LicenseRef-Proprietary": 2}, rep)
check("the record is not shipped: it lives outside public/", not os.path.exists(os.path.join(game, "public", "LICENSE.assets.json")))

# 2. Third-party restricted assets stay restricted, even under a project-wide first-party record.
stock = asset(game, "public/vendor/stock.svg", "00ff00")
write(stock + ".license.json", {"license": "LicenseRef-Proprietary", "attribution": "Stock Co."})
nc = asset(game, "public/vendor/texture.svg", "0000ff")
write(os.path.join(game, "public", "vendor", "LICENSE.assets.json"), {"texture.svg": {"license": "CC-BY-NC-4.0", "attribution": "Someone"}})
write(os.path.join(game, "LICENSE.assets.json"), {"*": {"license": "LicenseRef-Proprietary", "first_party": True}})
for p in (stock, nc): C.register(p, project=game)
rep = C.license_report(game)
check("a third-party proprietary file (its own sidecar) stays restricted under a root '*' first-party record",
      "public/vendor/stock.svg" in rep["restricted"].get("LicenseRef-Proprietary", []), rep)
check("a third-party non-commercial file (nearer folder record) stays restricted", "public/vendor/texture.svg" in rep["restricted"].get("CC-BY-NC-4.0", []), rep)
check("the project's own files are still cleared beside them", set(rep["first_party"].get("LicenseRef-Proprietary", [])) == {"public/icon.svg", "public/og.svg"}, rep)

# 3. Declarations are read at report time; first_party must be the literal true.
late = project("late")
pic = asset(late, "art/hero.svg")
C.register(pic, project=late)
check("a file with no record is UNKNOWN", C.license_report(late)["unknown"] == ["art/hero.svg"])
write(os.path.join(late, "LICENSE.assets.json"), {"art/hero.svg": {"license": "LicenseRef-Proprietary", "first_party": "yes"}})
rep = C.license_report(late)
check("a declaration added after cataloguing fills the licence without a rescan", rep["unknown"] == [] and rep["by_license"] == {"LicenseRef-Proprietary": 1}, rep)
check('"first_party": "yes" is not a declaration (only true is)', "LicenseRef-Proprietary" in rep["restricted"], rep)

# 4. GITCRAFT's own id for project-owned output, and ownership recorded at registration.
own = project("own")
gen = asset(own, "assets/gen.svg")
C.register(gen, license="LicenseRef-Project-Owned", project=own)
reg = asset(own, "assets/reg.svg", "123456")
C.register(reg, license="LicenseRef-Proprietary", source={"type": "manual", "first_party": True}, project=own)
rep = C.license_report(own)
check("LicenseRef-Project-Owned is first-party", "LicenseRef-Project-Owned" in rep["first_party"] and rep["restricted"] == {}, rep)
check("first_party recorded in the registration source counts", "assets/reg.svg" in rep["first_party"].get("LicenseRef-Proprietary", []), rep)

# 5. Unchanged behaviour: a per-folder record keyed by file name, and a plain third-party NC asset.
old = project("old")
a = asset(old, "sfx/a.svg"); write(os.path.join(old, "sfx", "LICENSE.assets.json"), {"a.svg": {"license": "CC0-1.0"}})
b = asset(old, "sfx/b.svg", "abcdef"); write(b + ".license.json", {"license": "CC-BY-NC-4.0", "attribution": "X"})
for p in (a, b): C.register(p, project=old)
rep = C.license_report(old)
check("a folder record keyed by file name still applies", rep["by_license"].get("CC0-1.0") == 1, rep)
check("a third-party NC asset is restricted as before", rep["restricted"] == {"CC-BY-NC-4.0": ["sfx/b.svg"]}, rep)

print(f"\n{'all passed' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
