import json, sys, statistics as st
from pathlib import Path
sys.path.insert(0,"D:/aai work/anime_studio_merge/director")
import voice_cast as v
pack=Path("D:/aai work/anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva")
out=Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva")
man=json.load(open(out/"eleven_manifest.json",encoding="utf-8"))
slots=v.load_slots(pack); plan=v.load_plan(pack)
rate={}
for r in man["lines"]:
    if r.get("ok") and not (r.get("settings") or {}).get("speed"):
        rate.setdefault((r["lang"],r["voice"]),[]).append((r["seconds"]-0.2)/len(r["text"]))
rate={k:st.mean(x) for k,x in rate.items()}
mean={lg:st.mean([x for (l,w),x in rate.items() if l==lg]) for lg in ("en","hi")}
F=json.load(open("D:/aai work/anime_studio_merge/research/FINAL_TEXT_DRAFT.json",encoding="utf-8"))
spk={l["id"]:l["voice"] for l in plan["lines"]}
bad=[]
for lid,t in F.items():
    for lg in ("en","hi","mr"):
        n=len(v.voices.prep_text(t[lg])); k=(lg,spk[lid]); known=k in rate
        rt=rate.get(k) or mean["hi" if lg=="mr" else lg]
        tempo=(rt*n+0.2)/slots[lid]
        t.setdefault("_",{})[lg]=(n,round(tempo,2),"m" if known else "est")
        if tempo>1.22: bad.append((lid,lg,n,round(tempo,2),"m" if known else "est",t[lg]))
print("predicted tempo > 1.22 (needs trimming):",len(bad))
for b in bad: print(b)
