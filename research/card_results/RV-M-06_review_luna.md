- `a_prompt()` does not produce the required eight sentences or include all required content. It conditionally adds a style anchor and light, adds two sentences per cast member, and never describes the space or continuity. Replace the variable assembly with exactly eight sentence slots for style, shot, composition, subject, space, light, continuity, and frame law; enforce the eight-sentence count and 110-word limit.

- A jobs can silently omit both required style inputs. The defaults are `STYLE_CHIP = None` and `STYLE_ANCHOR = None`, and `a_chips` adds the chip only when truthy. Require both inputs when building an A job and raise `KeyframeJobError` if either is missing.

- B generation does not enforce the card’s hard rules. `b_instruction()` only limits the number of changes; it does not reject screen-side flips without a qualifying L10 turn record and shot duration, key-light-side changes, prop-count changes, or facing changes over 90 degrees per 1.5 seconds. Add validation for each rule before constructing B, and omit or reject B when a rule fails.

- The required test name `test_b_text_form` is absent: the implementation provides `test_b_text_form_opus_example`. Rename it to the card’s listed name so the required test is discoverable under that name.

- `test_a_prompt_has_no_digits_coords` removes `"9:16"` before checking for digits, so it cannot verify that the required frame-law text is present. Assert that `FRAME_LAW` is in the prompt, then check digits after removing only that exact required phrase.

VERDICT: FIX-FIRST