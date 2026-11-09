import csv, json
CSV = 'D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/approval_sheet_18x3.csv'
PK = 'D:/aai work/anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/shots.json.bak_pre_v2text'
orig = {}
for s in json.load(open(PK, encoding='utf-8')):
    a, sid = s['audio_and_dialogue_track'], s['id']
    for lg in ('en', 'hi', 'mr'):
        if a['narration_by_lang'].get(lg, {}).get('text'):
            orig[(sid + '-N', lg)] = a['narration_by_lang'][lg]['text']
        for k, d in enumerate(a['dialogue_by_lang'][lg], 1):
            orig[(sid + '-D' + str(k), lg)] = d['text']

# (line, who, start, window_end)  window_end = latest second the audio may end at
W = [
 ('SHOT-001-N','N',0.5,7.04), ('SHOT-002-N','N',0.3,6.33), ('SHOT-003-N','N',0.3,2.15),
 ('SHOT-003-D1','MUNIS',2.3,4.45), ('SHOT-003-D2','MARK',4.6,7.4), ('SHOT-004-N','N',0.4,9.88),
 ('SHOT-005-N','N',0.3,4.05), ('SHOT-005-D1','KAMA',4.2,8.2), ('SHOT-006-D1','BRAHMA',0.3,4.2),
 ('SHOT-006-N','N',4.3,8.46), ('SHOT-007-D1','KAMA',0.2,2.4), ('SHOT-007-N','N',3.2,8.46),
 ('SHOT-008-D1','SHIVA',1.2,5.0), ('SHOT-008-N','N',5.1,9.88), ('SHOT-009-D1','BRAHMA',1.2,5.8),
 ('SHOT-009-N','N',5.9,9.88), ('SHOT-010-D1','KAMA',0.6,3.65), ('SHOT-010-N','N',3.8,6.33)]
K = {'N':(0.080,0.085,0.090),'BRAHMA':(0.083,0.135,0.105),'SHIVA':(0.080,0.078,0.083),
     'MARK':(0.085,0.076,0.080),'MUNIS':(0.078,0.085,0.090),'KAMA':(0.082,0.085,0.090)}

# NEW text only where the approved text does not fit; everything else keeps the approved text
NEW = {
 ('SHOT-003-N','en'): "At dawn, sages came.",
 ('SHOT-003-N','mr'): "पहाटे ऋषी आले.",
 ('SHOT-003-D1','en'): "How was Sati born and wed?",
 ('SHOT-003-N','hi'): "सुबह मुनि सवाल लेकर आए।",
 ('SHOT-003-D1','hi'): "सती कैसे जन्मीं और ब्याही?",
 ('SHOT-003-D1','mr'): "सतीचा जन्म आणि लग्न कसं?",
 ('SHOT-003-D2','en'): "Listen. Brahma told it first.",
 ('SHOT-003-D2','mr'): "ऐका. ब्रह्मदेवांनी आधी हे सांगितलं.",
 ('SHOT-005-N','en'): "Then another came from his mind, golden yellow.",
 ('SHOT-005-N','mr'): "मग त्यांच्या मनातून आणखी एक आला, सोनेरी.",
 ('SHOT-005-D1','hi'): "प्रभु, मेरा काम क्या है? घर दीजिए, पत्नी भी।",
 ('SHOT-006-D1','en'): "Your flower arrows win every heart, even Shiva's.",
 ('SHOT-006-D1','hi'): "तुम्हारे बाण शिव को भी जीतेंगे।",
 ('SHOT-006-D1','mr'): "तुझे बाण सर्वांचं मन जिंकतील, शिवांचंही.",
 ('SHOT-008-D1','en'): "Brahma, she's your own daughter. How could you?",
 ('SHOT-008-D1','mr'): "ब्रह्मदेव, ती तुमचीच मुलगी आहे. मन कसं डळमळलं?",
 ('SHOT-009-D1','en'): "You shot at me? Fire from Mahadeva's eye will burn you.",
 ('SHOT-009-D1','hi'): "बाण? महादेव की आँख तुम्हें जलाएगी।",
 ('SHOT-009-D1','mr'): "माझ्यावर बाण? महादेवांच्या डोळ्यांची आग जाळेल.",
 ('SHOT-010-D1','hi'): "आपने कहा, सब पर चलाओ। मेरी गलती क्या?",
 ('SHOT-010-D1','mr'): "सर्वांवर सोडा म्हणालात! माझी चूक काय?",
 ('SHOT-010-N','hi'): "क्या ब्रह्मा जी श्राप लौटाएँगे?",
}
li = {'en':0,'hi':1,'mr':2}
out, rep = {}, []
for line, who, t0, tend in W:
    win = tend - t0
    for lg in ('en','hi','mr'):
        t = NEW.get((line,lg), orig[(line,lg)])
        pred = len(t) * K[who][li[lg]]
        sp = pred / win
        out[f"{line}.{lg}"] = {"text": t, "chars": len(t), "window_s": round(win,2), "start_s": t0,
                                "pred_s": round(pred,2), "speedup": round(sp,2), "changed": t != orig[(line,lg)]}
        rep.append(f"{line} {lg} chars={len(t)} win={win:.2f} pred={pred:.2f} speedup={sp:.2f}{' NEW' if (line,lg) in NEW else ''} | {t}")
json.dump(out, open('D:/aai work/tmp_fit/final_text.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
open('D:/aai work/tmp_fit/final_report.txt','w',encoding='utf-8').write("\n".join(rep))
