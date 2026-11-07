"""Colour-blind panel helper for the G4 QA sheet (WP9 / A16): Machado, Oliveira, Fernandes 2009 deuteranopia at severity 1.0.
The matrix is applied in linear RGB; sRGB <-> linear uses 8-bit lookup tables.
ponytail: 8-bit linear quantisation, very dark greys can move a few levels; upgrade path: float maths when numpy is allowed."""
from PIL import Image

MACHADO_DEUTERANOPIA = (
    (0.367322, 0.860646, -0.227968),
    (0.280085, 0.672501, 0.047413),
    (-0.011820, 0.042940, 0.968881),
)
THUMB_WIDTH = 270
_CONVERT_MATRIX = tuple(x for row in MACHADO_DEUTERANOPIA for x in (*row, 0.0))


def _to_linear(v):
    c = v / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(x):
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


LINEAR_LUT = [round(_to_linear(v) * 255) for v in range(256)]
SRGB_LUT = [min(255, max(0, round(_to_srgb(v / 255) * 255))) for v in range(256)]


def simulate_deuteranopia(img):
    """RGB image of the same size: sRGB -> linear -> Machado matrix (clipped) -> sRGB."""
    linear = img.convert("RGB").point(LINEAR_LUT * 3)
    return linear.convert("RGB", _CONVERT_MATRIX).point(SRGB_LUT * 3)


def thumbnail(img, width=THUMB_WIDTH):
    """RGB copy scaled to `width` px wide, aspect kept (LANCZOS)."""
    rgb = img.convert("RGB")
    height = max(1, round(rgb.height * width / rgb.width))
    return rgb.resize((width, height), Image.Resampling.LANCZOS)


def panel(img):
    """The 270 px thumbnail (left) beside the 270 px thumbnail of its deuteranopia simulation (right)."""
    original = thumbnail(img)
    simulated = simulate_deuteranopia(original)
    out = Image.new("RGB", (original.width + simulated.width, original.height))
    out.paste(original, (0, 0))
    out.paste(simulated, (original.width, 0))
    return out
