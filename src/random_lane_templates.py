"""Option and GET READY matching adapted with permission from RandomLaneAnalysis_OCR.

Matching helpers and thresholds follow iidx_main.py. The adapter consumes RGB
Spout frames; it does not import the upstream application or its Windows UI.
"""

from pathlib import Path

import cv2
import numpy as np

def cv_imread_unicode(path: Path, flags=cv2.IMREAD_UNCHANGED):
    """Read an image from a Windows path that may contain Japanese characters."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    # cv2.imread() can fail on some Windows/OpenCV combinations when the path
    # contains non-ASCII characters. Read the raw bytes with NumPy/Python, then
    # let OpenCV decode the image from memory instead.
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        raise OSError(f"Image file is empty or unreadable: {path}")

    img = cv2.imdecode(data, flags)
    if img is None:
        raise OSError(f"OpenCV could not decode image: {path}")
    return img

REF_W = 1920

REF_H = 1080

OPTION_TEMPLATE_FILES = {
    "ANCHOR": "OP_CURRENT_SCORE.png",
    "MIRROR": "Op.MIRROR.png",
    "RANDOM": "Op.RANDOM.png",
    "R-": "Op.R-.png",
    "S-": "Op.S-.png",
}

ANCHOR_EXPECTED = {
    "1P_GRAPH_LEFT":  (551, 873),
    "1P_GRAPH_RIGHT": (1512, 873),
    "2P_GRAPH_LEFT":  (10, 873),
    "2P_GRAPH_RIGHT": (971, 873),
}

ANCHOR_MARGIN_X = 36

ANCHOR_MARGIN_Y = 20

ANCHOR_THRESHOLD = 0.88

OPTION_THRESHOLD = 0.82

PREFIX_THRESHOLD = 0.60

PREFIX_MARGIN = 0.05

OPTION_REL = (-5, 38, 205, 72)

OPTION_CONFIRM_FRAMES = 3

def scale_rect_option(rect, w, h):
    x1, y1, x2, y2 = rect
    sx, sy = w / REF_W, h / REF_H
    return (
        int(round(x1 * sx)),
        int(round(y1 * sy)),
        int(round(x2 * sx)),
        int(round(y2 * sy)),
    )

def best_match_option(search_gray, templ_gray):
    sh, sw = search_gray.shape[:2]
    th, tw = templ_gray.shape[:2]
    if sw < tw or sh < th or sw <= 0 or sh <= 0:
        return -1.0, (0, 0)
    res = cv2.matchTemplate(search_gray, templ_gray, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    maxv = float(maxv)
    if not np.isfinite(maxv):
        return -1.0, (0, 0)
    return maxv, maxloc

def anchor_search_roi(layout, anchor_w, anchor_h):
    ex, ey = ANCHOR_EXPECTED[layout]
    return (
        max(0, ex - ANCHOR_MARGIN_X),
        max(0, ey - ANCHOR_MARGIN_Y),
        min(REF_W, ex + anchor_w + ANCHOR_MARGIN_X),
        min(REF_H, ey + anchor_h + ANCHOR_MARGIN_Y),
    )

def candidate_layouts_for_side(side):
    if side == "1P":
        return ("1P_GRAPH_LEFT", "1P_GRAPH_RIGHT")
    return ("2P_GRAPH_LEFT", "2P_GRAPH_RIGHT")

def detect_layout_anchor(bgr, side, anchor_template):
    """Search only the two legal graph positions for the already-locked SIDE."""
    h, w = bgr.shape[:2]
    ah, aw = anchor_template.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    scored = []
    for layout in candidate_layouts_for_side(side):
        roi_ref = anchor_search_roi(layout, aw, ah)
        x1, y1, x2, y2 = scale_rect_option(roi_ref, w, h)
        search = gray[y1:y2, x1:x2]
        score, loc = best_match_option(search, anchor_template)
        abs_pos = (x1 + loc[0], y1 + loc[1])
        scored.append((score, layout, abs_pos))

    scored.sort(reverse=True, key=lambda x: x[0])
    best_score, best_layout, best_pos = scored[0]
    return best_score, best_layout, best_pos, scored

def classify_option(option_gray, option_templates):
    random_score, random_loc = best_match_option(
        option_gray, option_templates["RANDOM"]
    )
    mirror_score, _ = best_match_option(
        option_gray, option_templates["MIRROR"]
    )

    debug = {
        "r_score": -1.0,
        "s_score": -1.0,
        "prefix": "NONE",
    }

    if random_score >= OPTION_THRESHOLD:
        rh, rw = option_templates["RANDOM"].shape[:2]
        ph = max(
            option_templates["R-"].shape[0],
            option_templates["S-"].shape[0],
        )
        pw = max(
            option_templates["R-"].shape[1],
            option_templates["S-"].shape[1],
        )
        rx, ry = random_loc
        px2 = rx
        px1 = max(0, px2 - pw)
        py1 = max(0, ry + (rh - ph) // 2)
        py2 = min(option_gray.shape[0], py1 + ph)
        prefix_roi = option_gray[py1:py2, px1:px2]

        r_score, _ = best_match_option(prefix_roi, option_templates["R-"])
        s_score, _ = best_match_option(prefix_roi, option_templates["S-"])
        debug["r_score"] = r_score
        debug["s_score"] = s_score

        if (
            r_score >= PREFIX_THRESHOLD
            and r_score - s_score >= PREFIX_MARGIN
        ):
            debug["prefix"] = "R-"
            return "R-RANDOM", random_score, mirror_score, debug

        if (
            s_score >= PREFIX_THRESHOLD
            and s_score - r_score >= PREFIX_MARGIN
        ):
            debug["prefix"] = "S-"
            return "S-RANDOM", random_score, mirror_score, debug

        return "RANDOM", random_score, mirror_score, debug

    if mirror_score >= OPTION_THRESHOLD:
        return "MIRROR", random_score, mirror_score, debug

    return "UNKNOWN", random_score, mirror_score, debug

def load_option_templates(templates_dir):
    out = {}
    for key, filename in OPTION_TEMPLATE_FILES.items():
        img = cv_imread_unicode(templates_dir / filename, cv2.IMREAD_GRAYSCALE)
        if img is None or img.size == 0:
            raise OSError(f"Could not load OPTION template: {filename}")
        out[key] = img
    return out

GET_READY_SCALES = (1.00,)

GET_READY_SEARCH_X1 = 40

GET_READY_SEARCH_Y1 = 470

GET_READY_SEARCH_X2 = 560

GET_READY_SEARCH_Y2 = 620

GET_READY_APPEAR_SCORE = 0.62

GET_READY_DISAPPEAR_SCORE = 0.52

GET_READY_APPEAR_FRAMES = 3

GET_READY_DISAPPEAR_FRAMES = 3

def preprocess_get_ready(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (3, 3), 0)

def build_get_ready_templates(image):
    base = preprocess_get_ready(image)
    templates = []

    for scale in GET_READY_SCALES:
        width = max(1, int(round(base.shape[1] * scale)))
        height = max(1, int(round(base.shape[0] * scale)))
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        resized = cv2.resize(
            base, (width, height), interpolation=interpolation
        )
        templates.append((scale, resized))

    return templates

def find_best_get_ready_match(frame, templates, side="1P"):
    # Fast realtime search:
    # restrict matching to a small fixed ROI around the proven 1P GET READY
    # position instead of scanning the entire left half of 1920x1080.
    frame_h, frame_w = frame.shape[:2]

    if side == "2P":
        # Mirror only the search AREA, not the glyph template or key numbering.
        sx1 = frame_w - GET_READY_SEARCH_X2 * frame_w / 1920
        sx2 = frame_w - GET_READY_SEARCH_X1 * frame_w / 1920
    else:
        sx1 = GET_READY_SEARCH_X1 * frame_w / 1920
        sx2 = GET_READY_SEARCH_X2 * frame_w / 1920
    x1 = max(0, min(int(sx1), frame_w - 1))
    y1 = max(0, min(int(GET_READY_SEARCH_Y1 * frame_h / 1080), frame_h - 1))
    x2 = max(x1 + 1, min(int(sx2), frame_w))
    y2 = max(y1 + 1, min(int(GET_READY_SEARCH_Y2 * frame_h / 1080), frame_h))

    search_bgr = frame[y1:y2, x1:x2]
    search = preprocess_get_ready(search_bgr)
    search_h, search_w = search.shape[:2]

    best = (-1.0, 0, 0, 0, 0, 1.0)

    for scale, template in templates:
        template_h, template_w = template.shape[:2]

        if template_w > search_w or template_h > search_h:
            continue

        result = cv2.matchTemplate(
            search, template, cv2.TM_CCOEFF_NORMED
        )
        _, score, _, position = cv2.minMaxLoc(result)

        if score > best[0]:
            # Convert ROI-local coordinates back to full-frame coordinates.
            best = (
                float(score),
                int(position[0] + x1),
                int(position[1] + y1),
                int(template_w),
                int(template_h),
                float(scale),
            )

    return best


def match_one(search_gray, templ_gray, templ_mask):
    if search_gray.shape[0] < templ_gray.shape[0] or search_gray.shape[1] < templ_gray.shape[1]:
        return -1.0, (0, 0)
    result = cv2.matchTemplate(
        search_gray, templ_gray, cv2.TM_CCORR_NORMED, mask=templ_mask
    )
    # Masked matching can theoretically create non-finite values at degenerate
    # locations. Make them harmless before minMaxLoc.
    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return float(max_val), max_loc

TEMPLATE_SCRATCH = "SCRATCH.png"

SCRATCH_EXPECTED_POS = {
    "1P": (21, 729),
    "2P": (1758, 729),
}

SCRATCH_MARGIN_X = 35

SCRATCH_MARGIN_Y = 30

SCRATCH_THRESHOLD = {
    "1P": 0.93,
    "2P": 0.83,
}

SCRATCH_CONFIRM_FRAMES = 3

SCRATCH_CENTER_MASK_RADIUS_RATIO = 0.29

def load_scratch_template(path: Path):
    img = cv_imread_unicode(path, cv2.IMREAD_UNCHANGED)

    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        alpha = np.full(img.shape, 255, dtype=np.uint8)
    elif img.shape[2] == 4:
        bgr = img[:, :, :3].copy()
        alpha = img[:, :, 3].copy()
    else:
        bgr = img[:, :, :3].copy()
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = np.where(alpha >= 32, 255, 0).astype(np.uint8)

    h, w = mask.shape
    cx, cy = w // 2, h // 2
    radius = max(1, int(round(min(w, h) * SCRATCH_CENTER_MASK_RADIUS_RATIO)))
    cv2.circle(mask, (cx, cy), radius, 0, -1)

    if cv2.countNonZero(mask) < 20:
        raise ValueError("SCRATCH template mask has too few visible pixels.")
    return gray, mask

def scratch_roi_1920(side, templ_w, templ_h):
    ex, ey = SCRATCH_EXPECTED_POS[side]
    return (
        max(0, ex - SCRATCH_MARGIN_X),
        max(0, ey - SCRATCH_MARGIN_Y),
        min(1920, ex + templ_w + SCRATCH_MARGIN_X),
        min(1080, ey + templ_h + SCRATCH_MARGIN_Y),
    )

class PlayStartRecognizer:
    """Lock the option before GET READY, then start on its disappearance."""

    REQUIRED_FILES = tuple(OPTION_TEMPLATE_FILES.values()) + ('GET_READY.png', TEMPLATE_SCRATCH)

    def __init__(self, folder):
        folder = Path(folder)
        self.options = load_option_templates(folder)
        ready = cv_imread_unicode(folder / 'GET_READY.png', cv2.IMREAD_COLOR)
        self.scratch, self.scratch_mask = load_scratch_template(folder / TEMPLATE_SCRATCH)
        self.ready_templates = build_get_ready_templates(ready)
        if np.std(self.ready_templates[0][1]) < 1:
            raise ValueError("Invalid template: GET_READY.png")
        for name, image in self.options.items():
            if image.shape[0] < 2 or image.shape[1] < 2 or np.std(image) < 1:
                raise ValueError(f'Invalid template: {OPTION_TEMPLATE_FILES[name]}')
        self.reset()

    def reset(self):
        self.preplay = False
        self.scratch_count = 0
        self.layout_candidate = None
        self.layout_count = 0
        self.option = None
        self.candidate = None
        self.candidate_count = 0
        self.visible = False
        self.appear_count = 0
        self.disappear_count = 0
        self.started = False

    def observe(self, rgb, side):
        if self.started:
            return self.option
        if rgb.shape[:2] != (1080, 1920):
            return None
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        if not self.preplay:
            sh, sw = self.scratch.shape[:2]
            x1, y1, x2, y2 = scratch_roi_1920(side, sw, sh)
            gray = cv2.cvtColor(bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            score, _ = match_one(gray, self.scratch, self.scratch_mask)
            self.scratch_count = self.scratch_count + 1 if score >= SCRATCH_THRESHOLD[side] else 0
            if self.scratch_count < SCRATCH_CONFIRM_FRAMES:
                return None
            self.preplay = True
        if not self.visible and self.option is None:
            score, layout, (ax, ay), _ = detect_layout_anchor(bgr, side, self.options['ANCHOR'])
            if score >= ANCHOR_THRESHOLD and layout == self.layout_candidate:
                self.layout_count += 1
            else:
                self.layout_candidate = layout if score >= ANCHOR_THRESHOLD else None
                self.layout_count = 1 if self.layout_candidate else 0
            option = None
            if self.layout_count >= OPTION_CONFIRM_FRAMES:
                rx1, ry1, rx2, ry2 = OPTION_REL
                crop = bgr[max(0, ay + ry1):min(1080, ay + ry2),
                           max(0, ax + rx1):min(1920, ax + rx2)]
                if crop.size:
                    result, _, _, _ = classify_option(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), self.options)
                    option = 'REGULAR' if result == 'UNKNOWN' else result
            if option and option == self.candidate:
                self.candidate_count += 1
            else:
                self.candidate, self.candidate_count = option, 1 if option else 0
            if self.candidate_count >= OPTION_CONFIRM_FRAMES:
                self.option = option

        score = find_best_get_ready_match(bgr, self.ready_templates, side)[0]
        if not self.visible:
            self.appear_count = self.appear_count + 1 if score >= GET_READY_APPEAR_SCORE else 0
            if self.appear_count >= GET_READY_APPEAR_FRAMES:
                self.visible = True
        else:
            self.disappear_count = self.disappear_count + 1 if score <= GET_READY_DISAPPEAR_SCORE else 0
            if self.disappear_count >= GET_READY_DISAPPEAR_FRAMES:
                self.started = True
                # UNKNOWN must never become a normal chart when the anchor was absent.
                return self.option or 'UNKNOWN'
        return None
