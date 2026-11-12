- **Short edit requirement is not met.** The test marks the required 60-frame case as an expected failure:

  ```python
  @pytest.mark.xfail(
      strict=True, raises=ValueError,
      reason="H3 rules ... reject a 60-frame DYNAMIC cut ..."
  )
  def test_trimmed_short_shot():
  ```

  And the H3 trim planner rejects an outgoing dynamic trim outside the impact span:

  ```python
  if not a6 <= ed <= b6:
  ```

  For the card’s 60-frame edit, that check reports a problem instead of producing the requested trim record. Update the H3 trim rules so a 60-frame edit can use the 107-frame render and record `trim_in_frame=0`, `trim_out_frame=60`, and `tail_handle_frames=47`; then remove the `xfail` so `test_trimmed_short_shot` must pass.

VERDICT: FIX-FIRST.