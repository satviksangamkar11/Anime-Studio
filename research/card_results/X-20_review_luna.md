`stem_builder.py` calls `write_noduck` without the card’s required explicit target:

```python
nd_mp3, nd_before, nd_after, nd_gain = write_noduck(noduck, total, v)
```

Pass the named constant at the call site:

```python
nd_mp3, nd_before, nd_after, nd_gain = write_noduck(
    noduck, total, v, target_lufs=AUDITION_NODUCK_LUFS
)
```

VERDICT: FIX-FIRST.