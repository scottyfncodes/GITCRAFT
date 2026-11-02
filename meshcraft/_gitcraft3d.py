"""Load the shared gitcraft3d package by its path.

Inside the GITCRAFT sandbox only this tool's folder and gitcraft3d/ are readable, not the repo
root, so Python's importer cannot find gitcraft3d through sys.path; it is loaded directly.
`import _gitcraft3d` once, then `from gitcraft3d import …` works as usual."""
import importlib.util, os, sys

if "gitcraft3d" not in sys.modules:
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gitcraft3d")
    _spec = importlib.util.spec_from_file_location("gitcraft3d", os.path.join(_p, "__init__.py"), submodule_search_locations=[_p])
    _mod = importlib.util.module_from_spec(_spec); sys.modules["gitcraft3d"] = _mod; _spec.loader.exec_module(_mod)
