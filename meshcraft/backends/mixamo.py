"""Mixamo (Adobe) character animation, through its supported manual workflow.

Mixamo has no public API, and scripted downloads from its website are not a supported or
permitted access method, so MeshCraft never calls mixamo.com. It supports Mixamo in the
two legitimate directions:
  * to Mixamo: `prepare_upload` exports a character as an unrigged T-pose FBX, the file a
    person uploads at mixamo.com for auto-rigging.
  * from Mixamo: `apply` imports FBX animations a person downloaded ("FBX Binary",
    "Without Skin", 30 fps; "In Place" for locomotion) and merges them onto a character
    whose skeleton uses Mixamo's bone names (a Mixamo-rigged character, or any MeshCraft
    character: its procedural rig already uses the mixamorig:* names), then exports GLB
    with every clip.
Characters and animations from Mixamo are royalty-free for commercial projects; the raw
files must not be redistributed standalone (see docs/3d-licensing.md)."""

GUIDE = [
    "1. In MeshCraft, run mixamo_prepare_upload on the character asset (or use any unrigged T-pose FBX/OBJ).",
    "2. Sign in at https://www.mixamo.com with a free Adobe ID and choose Upload Character; place the rig markers if asked.",
    "3. Pick animations (e.g. Walking, Running, Jump, Idle, Sword And Shield Slash). Tick 'In Place' for locomotion.",
    "4. Download each as Format: FBX Binary (.fbx), Skin: Without Skin, Frames per Second: 30, Keyframe Reduction: none.",
    "   Download the character once 'With Skin' (T-pose) if you want Mixamo's own rig.",
    "5. Put the files inside a GITCRAFT root (e.g. <repo>/mixamo/) and run mixamo_apply with the character and the animation paths.",
    "6. MeshCraft matches clips by bone name, keeps every clip as a separate glTF animation and adds a new asset version.",
]

MIXAMO_CORE = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
               "RightShoulder", "RightArm", "RightForeArm", "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
               "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"]
