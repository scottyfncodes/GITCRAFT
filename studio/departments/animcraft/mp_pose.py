"""Runs in the isolated mocap venv (~/.gitcraft/studio/mocap-venv): MediaPipe Pose Landmarker (Apache-2.0,
BlazePose GHUM 3D) on CPU. Request: {model, frames: [png paths], fps}. Result per frame: 33 world landmarks
(metres, hip-centred, MediaPipe axes: x right, y down, z away from the camera) with visibility, and the 33
normalised image landmarks (for the overlay), or null when no person was found."""
import json, sys
req = json.load(open(sys.argv[-1])); res = {"frames": []}
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    single = len(req["frames"]) == 1
    opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=req["model"]),
                                        running_mode=vision.RunningMode.IMAGE if single else vision.RunningMode.VIDEO,
                                        num_poses=1, min_pose_detection_confidence=0.5, min_tracking_confidence=0.5)
    with vision.PoseLandmarker.create_from_options(opts) as lm:
        for i, f in enumerate(req["frames"]):
            img = mp.Image.create_from_file(f)
            r = lm.detect(img) if single else lm.detect_for_video(img, int(round(i * 1000.0 / req["fps"])))
            if not r.pose_world_landmarks:
                res["frames"].append(None); continue
            w, n = r.pose_world_landmarks[0], r.pose_landmarks[0]
            res["frames"].append({"world": [[p.x, p.y, p.z, p.visibility] for p in w], "image": [[p.x, p.y] for p in n]})
    res["size"] = [img.width, img.height]
except Exception as e:
    import traceback; traceback.print_exc(); res = {"error": f"{type(e).__name__}: {e}"}
json.dump(res, open(req["_result"], "w"))
