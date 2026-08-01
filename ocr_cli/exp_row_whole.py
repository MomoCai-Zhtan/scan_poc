import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["TESSDATA_PREFIX"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")
import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import structure as st

img = st.render_pages(r"1150702.pdf", 200)[1]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
row = g[384:561, 94:1567]
out = []
for scale in [1, 2, 3]:
    up = row if scale == 1 else cv2.resize(row, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    for psm in [3, 4, 6, 11]:
        for wl in ["", "-c tessedit_char_whitelist=0123456789"]:
            try:
                t = pytesseract.image_to_string(up, config=f"--psm {psm} {wl}".strip()).strip().replace(chr(10), "|")
                out.append(f"scale{scale} psm{psm} wl={'Y' if wl else 'N'}: {t!r}")
            except Exception as e:
                out.append(f"scale{scale} psm{psm}: ERR {e}")
    out.append("---")
open(os.path.join("debug", "p2_r1_whole.txt"), "w", encoding="utf-8").write("\n".join(out))
print("done")
