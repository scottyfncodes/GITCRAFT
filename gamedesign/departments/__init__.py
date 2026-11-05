"""The analysis departments. Each module exposes NAME, TITLE, CATEGORY and analyse(model, ctx) -> report.

A report is {"dept", "title", "metrics", "findings", "strengths", "coverage", "viz"}; a finding is built with
base.finding(). The registry is a list so new departments (an AudioCraft-for-design, a UICraft) plug in by
adding a module here; ExperienceCraft runs last because it reads the other reports."""
from . import levelcraft, missioncraft, storycraft, progressioncraft, experiencecraft

REGISTRY = [levelcraft, missioncraft, storycraft, progressioncraft, experiencecraft]


def run_all(M, ctx):
    reports = {}
    for d in REGISTRY:
        ctx["reports"] = reports
        reports[d.NAME] = d.analyse(M, ctx)
    return reports
