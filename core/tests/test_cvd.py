"""core.cvd: Machado 2009 deuteranopia simulation, 270 px thumbnail and the colour-blind panel. Pillow only, no network."""
from PIL import Image

from core.cvd import panel, simulate_deuteranopia, thumbnail


def pixel(img, xy=(0, 0)):
    return img.convert("RGB").getpixel(xy)


def test_grey_stays_grey_within_two_levels():
    out = simulate_deuteranopia(Image.new("RGB", (4, 4), (128, 128, 128)))
    r, g, b = pixel(out)
    assert all(abs(c - 128) <= 2 for c in (r, g, b))


def test_pure_red_loses_red_and_gains_green_under_deuteranopia():
    r, g, b = pixel(simulate_deuteranopia(Image.new("RGB", (4, 4), (255, 0, 0))))
    assert r < 255 - 80        # R drops by more than 80
    assert g > 0 + 40          # G rises by more than 40


def test_white_stays_white_within_three_levels():
    r, g, b = pixel(simulate_deuteranopia(Image.new("RGB", (4, 4), (255, 255, 255))))
    assert all(c >= 255 - 3 for c in (r, g, b))


def test_simulation_keeps_size_and_returns_rgb_for_other_modes():
    out = simulate_deuteranopia(Image.new("L", (7, 5), 90))
    assert out.size == (7, 5) and out.mode == "RGB"
    out = simulate_deuteranopia(Image.new("RGBA", (3, 2), (10, 200, 30, 255)))
    assert out.size == (3, 2) and out.mode == "RGB"


def test_simulation_handles_a_one_pixel_image():
    assert simulate_deuteranopia(Image.new("RGB", (1, 1), (200, 40, 40))).size == (1, 1)


def test_thumbnail_is_270_wide_and_keeps_the_aspect_ratio():
    out = thumbnail(Image.new("RGB", (1920, 1080), (1, 2, 3)))
    assert out.size == (270, 152)                      # 1080 * 270 / 1920 = 151.875 -> 152
    assert out.mode == "RGB"


def test_thumbnail_of_a_one_pixel_image_is_270_square():
    assert thumbnail(Image.new("RGB", (1, 1), (9, 9, 9))).size == (270, 270)


def test_panel_is_two_thumbnails_side_by_side():
    img = Image.new("RGB", (1920, 1080), (255, 0, 0))
    out = panel(img)
    assert out.size == (2 * 270, 152)                  # 540 wide: original thumbnail + simulation thumbnail
    left, right = out.crop((0, 0, 270, 152)), out.crop((270, 0, 540, 152))
    assert left.tobytes() == thumbnail(img).tobytes()
    assert pixel(right) != pixel(left)                 # the right panel is the simulation, not a copy


def test_panel_of_a_one_pixel_image_does_not_crash():
    assert panel(Image.new("RGB", (1, 1), (0, 0, 0))).size == (540, 270)
