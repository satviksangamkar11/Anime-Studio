`window_levels_db` counts a final partial window as a full `window_sec` window, so `check_no_silence` can reject audio whose actual quiet span is at or below the limit. For example, a 0.305-second file at 10 ms windows produces 31 quiet windows and is reported as 0.31 seconds.

Exact fix: calculate the duration of each window from its actual sample count, and sum those durations for each quiet run instead of multiplying the run length by `window_sec`.

The listed 0.5-second silence failure and low-noise-bed pass tests are present. The low-noise fixture is a tone, though, so it does not test a noise bed as the card specifies.

VERDICT: FIX-FIRST