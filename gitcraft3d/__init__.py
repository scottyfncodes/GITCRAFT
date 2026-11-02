"""gitcraft3d: the 3D Department's shared foundation (standard library only).

Used by both 3D servers so there is one implementation of each:
  library.py   the versioned asset library (one for MeshCraft and ForgeCraft)
  jobs.py      job records, retry ladder, ForgeCraft orchestration jobs and their MeshCraft children
  hardware.py  the machine/capability probe (both servers' hardware_probe)
  routing.py   the router + rules.json (ForgeCraft's route/generate, MeshCraft's route advice, the UI)
Ownership: routing and jobs follow ForgeCraft's orchestration needs; the library format follows
MeshCraft's deliverables (files by kind, SHA-256, same_as), extended with ForgeCraft annotations.
"""
