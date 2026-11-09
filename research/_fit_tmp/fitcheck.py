import json,sys
sys.path.insert(0,'D:/aai work/anime_studio_merge/director')
import voice_cast as vc
man=json.load(open('D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/eleven_manifest.json',encoding='utf-8'))
fin=json.load(open('D:/aai work/tmp_fit/final_text.json',encoding='utf-8'))
have={}
for r in man['lines']:
    if r.get('ok'):
        have[r['id']]=r   # newest wins
out=[];k_new={}
for id_,v in fin.items():
    r=have.get(id_)
    if not r: out.append(f"{id_} NO CLIP"); continue
    want=vc.voices.prep_text(v['text'])
    cur = (r['text']==want)
    sp=r['seconds']; win=v['window_s']
    out.append(f"{id_:15} {'CUR ' if cur else 'OLD '} sec={sp:5.2f} win={win:5.2f} raw_tempo={sp/win:4.2f} trim_tempo={(sp-0.2)/win:4.2f} pred={v['pred_s']} chars={v['chars']} s/ch={(sp-0.2)/max(1,len(want)):.3f} {r['voice']}")
open('D:/aai work/tmp_fit/fitcheck.txt','w',encoding='utf-8').write("\n".join(out))
