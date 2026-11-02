"""Template registry. A template module defines META, default_roles(params) and build(ctx)."""
import importlib, pkgutil

def _modules():
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_"):
            yield importlib.import_module(f"{__name__}.{m.name}")

def registry():
    return {mod.META["id"]: mod for mod in _modules() if hasattr(mod, "META")}

def describe(mod):
    m = dict(mod.META)
    m["module"] = mod.__name__
    return m
