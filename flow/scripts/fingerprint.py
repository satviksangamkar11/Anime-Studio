"""64-bit dHash (difference hash) for the approved-picture check. Pillow only; shared by download_queue.py and file_flow_download.py."""
from PIL import Image


def dhash_image(im: Image.Image) -> str:
    """Grayscale, shrink to 9x8, bit = pixel brighter than its right neighbour: 8 rows x 8 bits, as 16 hex chars."""
    px = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return f"{bits:016x}"


def dhash_file(path) -> str:
    with Image.open(path) as im:
        return dhash_image(im)


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()
