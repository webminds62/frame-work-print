CAMERA_PRESETS = [
    {
        "id": "static",
        "label": "Static",
        "wan_pose": "Static",
        "suffix": "",
    },
    {
        "id": "dolly_in",
        "label": "Dolly In",
        "wan_pose": "Zoom In",
        "suffix": "slow cinematic dolly in, camera pushing toward the subject",
    },
    {
        "id": "dolly_out",
        "label": "Dolly Out",
        "wan_pose": "Zoom Out",
        "suffix": "slow cinematic dolly out, camera pulling away from the subject",
    },
    {
        "id": "pan_left",
        "label": "Pan Left",
        "wan_pose": "Pan Left",
        "suffix": "smooth cinematic pan left",
    },
    {
        "id": "pan_right",
        "label": "Pan Right",
        "wan_pose": "Pan Right",
        "suffix": "smooth cinematic pan right",
    },
    {
        "id": "crane_up",
        "label": "Crane Up",
        "wan_pose": "Pan Up",
        "suffix": "crane up, camera rising through the scene",
    },
    {
        "id": "crane_down",
        "label": "Crane Down",
        "wan_pose": "Pan Down",
        "suffix": "crane down, camera descending through the scene",
    },
    {
        "id": "orbit",
        "label": "Orbit",
        "wan_pose": "ClockWise (CW)",
        "suffix": "orbital camera move circling the subject",
    },
    {
        "id": "handheld",
        "label": "Handheld",
        "wan_pose": "Static",
        "suffix": "subtle handheld camera, organic micro-shake, documentary feel",
    },
]

FORMATS = [
    {
        "id": "16x9",
        "label": "16:9 Landscape",
        "ratio": "16:9",
        "sizes": {
            "fast": {"wan": [832, 480], "ltx": [768, 512], "flux": [640, 384]},
            "quality": {"wan": [1280, 720], "ltx": [1216, 704], "flux": [768, 448]},
        },
    },
    {
        "id": "9x16",
        "label": "9:16 Vertical",
        "ratio": "9:16",
        "sizes": {
            "fast": {"wan": [480, 832], "ltx": [512, 768], "flux": [384, 640]},
            "quality": {"wan": [720, 1280], "ltx": [704, 1216], "flux": [448, 768]},
        },
    },
    {
        "id": "1x1",
        "label": "1:1 Square",
        "ratio": "1:1",
        "sizes": {
            "fast": {"wan": [640, 640], "ltx": [640, 640], "flux": [512, 512]},
            "quality": {"wan": [768, 768], "ltx": [768, 768], "flux": [768, 768]},
        },
    },
]

QUALITY_LEVELS = [
    {"id": "quality", "label": "Quality 720p", "steps": {"wan": 40, "ltx": 36, "flux": 8}},
    {"id": "fast", "label": "Fast 480p", "steps": {"wan": 30, "ltx": 30, "flux": 4}},
]

DURATIONS = [
    {"id": "3s", "label": "3 seconds", "seconds": 3},
    {"id": "5s", "label": "5 seconds", "seconds": 5},
]

DEFAULT_NEGATIVES = {
    "video": "low quality, worst quality, deformed, distorted, blurry, overexposed, underexposed, watermark, subtitles, extra fingers, bad anatomy, jpeg artifacts",
    "still": "low quality, blurry, extra fingers, bad anatomy, watermark",
}

CINEMATIC_PREFIX = "sharp focus, detailed skin and fabric, natural lighting"


def camera_by_id(camera_id):
    for item in CAMERA_PRESETS:
        if item["id"] == camera_id:
            return item
    return CAMERA_PRESETS[0]


def format_by_id(format_id):
    for item in FORMATS:
        if item["id"] == format_id:
            return item
    return FORMATS[0]


def quality_by_id(quality_id):
    for item in QUALITY_LEVELS:
        if item["id"] == quality_id:
            return item
    return QUALITY_LEVELS[0]


def size_for(format_id, family, quality_id="quality"):
    fmt = format_by_id(format_id)
    quality_id = quality_id if quality_id in ("fast", "quality") else "quality"
    family = family if family in ("wan", "ltx", "flux") else "wan"
    return fmt["sizes"][quality_id][family]


def steps_for(family, quality_id="quality"):
    quality = quality_by_id(quality_id)
    family = family if family in quality["steps"] else "wan"
    return quality["steps"][family]


def frames_for(family, seconds):
    seconds = 5 if seconds not in (3, 5) else seconds
    if family == "wan":
        return 49 if seconds == 3 else 81
    if family == "ltx":
        return 73 if seconds == 3 else 97
    return 1


def apply_prompt(prompt, camera_id, cinematic=True, family="wan"):
    text = (prompt or "").strip()
    extras = []
    if cinematic and text:
        extras.append(CINEMATIC_PREFIX)
    camera = camera_by_id(camera_id)
    if family != "still" and camera["id"] != "static":
        extras.append(camera["suffix"])
    elif family != "still" and camera["id"] == "static":
        extras.append(camera["suffix"])
    extras = [item for item in extras if item]
    if extras:
        text = f"{text}, {', '.join(extras)}" if text else ", ".join(extras)
    return text
