"""Side-by-side review sheet of candidate images with labels.  python contact.py out.jpg label1=img1 label2=img2 ..."""
import sys
from PIL import Image, ImageDraw

out, pairs = sys.argv[1], [a.split("=", 1) for a in sys.argv[2:]]
ims = [(lab, Image.open(p).convert("RGB")) for lab, p in pairs]
h = 420
ims = [(lab, im.resize((int(im.width * h / im.height), h))) for lab, im in ims]
sheet = Image.new("RGB", (sum(im.width for _, im in ims) + 10 * (len(ims) + 1), h + 50), "white")
x = 10
for lab, im in ims:
    sheet.paste(im, (x, 40))
    ImageDraw.Draw(sheet).text((x, 12), lab, fill="black")
    x += im.width + 10
sheet.save(out, quality=90)
