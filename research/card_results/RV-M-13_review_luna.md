`prepare_chain` does not advance the chain depth:

```python
return {"png": png, "depth": depth, "header": chain_header(state)}
```

If `depth` is the current clip’s depth, the returned next-step depth stays unchanged. Repeated calls can therefore keep chaining past depth 2 without refusal. Return `depth + 1`, and refuse or re-anchor when that next depth exceeds `MAX_CHAIN_DEPTH`. Add a test that chains successive calls and verifies the third link is refused.

VERDICT: FIX-FIRST.