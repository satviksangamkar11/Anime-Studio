`box_problems` accepts inverted boxes as safe. For example, `(500, 500, 400, 600)` produces no problems even though `x1 < x0`, so the frame check can report an invalid OCR box as OK.

Faulty line: `x0, y0, x1, y1 = box`

Exact fix: after unpacking, reject boxes where `x0 > x1` or `y0 > y1` (and reject non-finite coordinates) by adding a problem before checking the safe-box bounds.

VERDICT: FIX-FIRST