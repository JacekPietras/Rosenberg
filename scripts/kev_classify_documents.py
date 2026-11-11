#!/usr/bin/env python3
"""Dry-run historical-family classification with a local Kev /v1/systemone."""
import argparse, hashlib, json, math, sys, time, urllib.error, urllib.request
from pathlib import Path

FAMILY_CHOICES = ('franconian', 'schenk', 'monch', 'rorschach', 'czech', 'lengenfelder', 'orsini', 'brandenburg')
CHOICES = FAMILY_CHOICES + ("other",)
TEXT_FIELDS = ("german", "latin", "summary")
DEFAULT_QUESTION = "Which listed historical family or non-family category best describes this document?"
REF = (
    "Classify the document using the people and actions in its German/Latin source text, citation, "
    "date, place and title. Identify a historical family from a person's full style together with "
    "holdings, office, relatives or transaction context; exact pedigree placement is not required. "
    "Witnesses, guarantors, spouses and other participants count. A family member may act outside the"
    " home region. Historical spellings vary. Distinguish explicit Schenk, Mönch/Münch/Monachus and "
    "Lengenfelder/Lengenvelder family styles from the ordinary Franconian Rosenbergs. Do not assign a"
    " family from a common given name, a place alone, the issuing archive, or another person's title."
    " Von, de and zu can all occur in noble styles or descriptions of origin/residence: the particle "
    "alone does not decide family versus place. Other covers non-target material: settlements, "
    "castles, streets, buildings and addresses called Rosenberg; residents described by origin or "
    "location; modern private individuals with the surname; and positively identified noble houses "
    "outside the eight targets. Do not infer family membership or place-only relevance from von/de/zu"
    " alone. A noble von Rosenberg zu Boxberg remains a target-family participant. Low confidence "
    "among the eight families is represented by their scores, not by an uncertain or mixed answer. If"
    " several target families participate, select the one most directly represented; other "
    "probabilities may indicate alternatives but are not independent multi-family probabilities. "
    "There is no mixed or uncertain answer; show the distribution over the available substantive "
    "categories. Northern Rosenbergs with Bredow are not proved identical to Barby/Saale Rosenburg. "
    "Friedrich Voit/Voyt called der Frank/Franch near Sulzbach is not automatically the Franconian "
    "Bauland house. A Bohemian Orsini ancestry claim alone does not identify the Austrian Orsini "
    "house."
)
CRITERIA = {
    "franconian": "Franconian/Bauland/Odenwald von Rosenberg: people acting around Boxberg, Wölchingen/Wulchingen, Lauda/Luden, Schüpf/Unterschüpf, Haltenbergstetten, Bartenstein, Waldmannshofen, Mudau or Wildenberg. Context includes Würzburg tithes and church affairs, Mainz or Palatine service, Vogt/Amtmann of Lauda or Wildenberg, Vizedom of Heidelberg/Amberg. Eberhard, Konrad, Arnold, Engelhard and Albrecht occur with such context. Distinguish explicit Schenk and Mönch bynames.",
    "schenk": "Schenk von Roßberg/Rossberg/Rossenberg/Rosperg, including Schenk von Rosenberg renderings with matching context: Würzburg cupbearer family, Roßberg/Schenkenschloss, Gadheim, Tauber-area transactions. Examples include Wolfram, Heinrich and Berthold, Eberhard with wife Agnes, Jörg/Georg with Margaretha von Thüngfeld. Not Schenk von Erbach, Limpurg or another Schenk house.",
    "monch": "Southwestern Mönch/Münch/Münich/Monachus von Rosenberg, including München von Rosenberg: Rosenberg near Osterburken, Mönchzell, Katzenelnbogen fiefs, Dallau, Eberbach, Steinsberg, Kirchardt or Palatine court service; Hans, Konrad/Contz, Dieter, Ruprecht, Peter occur in these settings. Gerlach Mönch of Elbing/Bütow/Osterode is not securely assigned to this southwestern lineage.",
    "rorschach": "Eastern Swiss Rorschach/Roschach and Rosenberg family: St Gallen abbey, Herisau, Berneck/Bernang, Zuckenriet, Rosenburg, Urstein, Lake Constance/Rhine valley. Eglolf/Egilolf/Egloff/Egli and Rudolf occur, sometimes as brothers with the same given name. Service abroad is possible, including Teutonic Order contexts with Swiss connections; no rigid branch-end date cutoff.",
    "czech": "South Bohemian Rožmberk/Rosenberg dynasty, de Rosis/z Rožmberka: Rožmberk castle, Hohenfurt/Vyšší Brod, Krumau/Český Krumlov, Wittingau/Třeboň, Vltava/Moldau. Wok/Vok, Peter/Petr, Jost/Jodok/Jošt, Ulrich/Oldřich and Johann/Jan; four brothers Peter, Jost, Ulrich, Johann in the 1300s. Passau, Haslach and Upper Austrian or imperial affairs can involve this family.",
    "lengenfelder": "Lengenfelder/Lengenfelderin/Lengenvelder/Lengfelder/von Lengenfeld with Rosenberg near Sulzbach in the Upper Palatinate: Sulzbach/Sultzpach, Kastl/Chastel, Pfeffertshofen, Gebenbach, Voyt/Franch and Löhlein associates. Konrad/Chunrad/Chunrat, Jeute/Jeutt and sons Konrad, Örtel, Heinrich, Friedrich are attested combinations. Bare Lengenfeld can concern unrelated Tirschenreuth or other namesakes.",
    "orsini": "Austrian Styrian/Carinthian Rosenberg, later Orsini/Ursini-Rosenberg: medieval ab dem Rosenberg/Graz/Graben context; later Johann Andreas, Georg Nikolaus, Wolfgang Andreas, Klagenfurt offices, Lerchenau, Grafenstein, Maria Loretto, Rosegg. Orsini double name authorized in 1684; earlier dates and bare Rosenberg do not exclude this house. Distinguish the Czech dynasty's Orsini ancestry claim.",
    "brandenburg": "Northern Rosenberg bearers in Brandenburg/Magdeburg context: Johann/Jan and Werner/Wernher, Plate/Altenplathow with Bredow in 1338, Kutzkow/Cutzekowe and Brandenburg episcopal/Magdeburg fiefs around 1400. Their home castle and link to Barby/Saale Rosenburg remain unproved; Burchard von Rosenburg alone is not sufficient identification.",
    "other": "Non-target material: Rosenberg as a village, city, castle, building, street or address; a resident described by that place; modern personal papers or lawsuits of people surnamed Rosenberg; or a known different noble house outside the eight targets, such as the Sulzbach Voit/Voyt. A location particle alone is not decisive.",
}

def h(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def expected_class(case, choices):
    expected = case.get("expected_class", case.get("expected"))
    if isinstance(expected, dict):
        positives = [k for k in FAMILY_CHOICES if expected.get(k) is True]
        if positives:
            expected = positives[0] if len(positives) == 1 else "mixed"
        else:
            matches = [k for k in choices if expected.get(k) is True]
            expected = matches[0] if len(matches) == 1 else None
    return expected if isinstance(expected, str) and expected in choices else None

def state(doc, reference):
    entries=[]
    for e in doc.get("entries",[]):
        obj={k:e[k] for k in ("source","title") if k in e}
        obj.update({k:e[k] for k in TEXT_FIELDS if isinstance(e.get(k),str) and e[k]})
        entries.append(obj)
    return {"reference":reference,"date":doc.get("date"),"place":doc.get("place"),"entries":entries}
def model_card(url,model,timeout):
    with urllib.request.urlopen(url.rstrip("/")+"/v1/models",timeout=timeout) as r: cards=json.load(r).get("models",[])
    c=next((x for x in cards if x.get("name")==model),None)
    if c is None: raise RuntimeError("requested model absent from /v1/models")
    ident={k:c.get(k) for k in ("name","run","base","lora","device","backend","dtype","temperature","release_date")}
    return c,h(ident)
def cases_from(args):
    if args.document:
        p=Path(args.document)
        yield str(p),p,{}
    elif args.cases:
        for n,line in enumerate(Path(args.cases).read_text(encoding="utf-8").splitlines(),1):
            if line.strip():
                c=json.loads(line); yield c.get("id",c.get("path",str(n))),Path(c["path"]),c
    else:
        for p in sorted(Path(args.documents_dir).glob("*.json")):
            try:
                d=json.loads(p.read_text(encoding="utf-8"))
                if d.get("deleted") or "to review" not in (d.get("label",[]) if isinstance(d.get("label"),list) else [d.get("label")] ): continue
                yield str(p),p,{}
            except Exception as e: print(f"skip {p}: {e}",file=sys.stderr)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    inputs=ap.add_mutually_exclusive_group()
    inputs.add_argument("--document",help="score one document JSON regardless of its current labels or deleted flag")
    inputs.add_argument("--cases")
    inputs.add_argument("--documents-dir",default="data/documents")
    ap.add_argument("--config");ap.add_argument("--output",default="/tmp/kev-classifications.jsonl");ap.add_argument("--base-url",default="http://127.0.0.1:8009");ap.add_argument("--model",default="kev-latest");ap.add_argument("--timeout",type=float,default=180);ap.add_argument("--limit",type=int);ap.add_argument("--threshold",type=float);ap.add_argument("--source-guards",action="store_true",help="also require direct source-text family attribution before accepting a predicted label");a=ap.parse_args()
    cfg=json.loads(Path(a.config).read_text()) if a.config else {"reference":REF,"criteria":CRITERIA}
    threshold=a.threshold if a.threshold is not None else cfg.get("acceptance_threshold",.6)
    eligible=cfg.get("eligible_choices",list(FAMILY_CHOICES))
    margin=cfg.get("minimum_margin",.15)
    guard_cfg=dict(cfg,acceptance_threshold=threshold,eligible_choices=eligible,minimum_margin=margin)
    choices=cfg.get("criteria",CRITERIA); question=cfg.get("question",DEFAULT_QUESTION)
    model, mf=model_card(a.base_url,a.model,a.timeout); qh=h({"reference":cfg.get("reference",REF),"question":question,"criteria":choices})
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True); cache={}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                r=json.loads(line)
                if r.get("status")=="ok": cache[(r["case_id"],r["source_fingerprint"],r["prompt_hash"],r["model_fingerprint"])]=r
            except Exception: pass
    rows=[]
    for i,(cid,path,case) in enumerate(cases_from(a)):
        if a.limit is not None and i>=a.limit: break
        if not path.is_absolute(): path=Path.cwd()/path
        try:
            doc=json.loads(path.read_text(encoding="utf-8")); st=state(doc,cfg.get("reference",REF)); rawstate=json.dumps(st,ensure_ascii=False); sf=h(st); key=(cid,sf,qh,mf); row=cache.get(key)
            if row is None:
                payload={"model":a.model,"state":rawstate,"questions":{"family":{"type":"choice","instructions":question,"criteria":choices}}}
                req=urllib.request.Request(a.base_url.rstrip("/")+"/v1/systemone",data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Content-Type":"application/json"},method="POST"); start=time.monotonic()
                with urllib.request.urlopen(req,timeout=a.timeout) as r: response=json.loads(r.read().decode()); reqid=r.headers.get("x-typesafe-request-id")
                ans=response.get("answers",{}).get("family",{}); probs=ans.get("probabilities"); pred=ans.get("choice")
                if pred not in choices or not isinstance(probs,dict) or set(probs)!=set(choices) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>1 for v in probs.values()): raise ValueError("malformed choice/probabilities")
                if abs(sum(probs.values())-1)>.005: raise ValueError("probabilities do not sum to 1 within .005")
                ranked=sorted(probs.values(),reverse=True)
                if probs[pred] < ranked[0]-.005: raise ValueError("choice is not the maximum-probability category")
                row={"status":"ok","case_id":cid,"path":str(path),"source_fingerprint":sf,"input_sha256":hashlib.sha256(rawstate.encode()).hexdigest(),"input_characters":len(rawstate),"prompt_hash":qh,"model":a.model,"model_id":response.get("model"),"model_fingerprint":mf,"model_card":model,"request_id":reqid,"raw_response":response,"prediction":pred,"probabilities":probs,"latency_seconds":time.monotonic()-start}
                row["expected"]=expected_class(case,choices)
                with out.open("a",encoding="utf-8") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
            row=dict(row,expected=expected_class(case,choices))
            rows.append(row);print(f"{cid}: {row['prediction']} ({row['probabilities'][row['prediction']]:.3f})",file=sys.stderr)
        except Exception as e:
            row={"status":"error","case_id":cid,"path":str(path),"error":str(e)};rows.append(row)
            with out.open("a",encoding="utf-8") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
            print(f"{cid}: ERROR {e}",file=sys.stderr)
    ok=[r for r in rows if r.get("status")=="ok" and isinstance(r.get("expected"),str)]
    accepted=[]; guard_rejections=[]
    for r in ok:
        ranked=sorted(r["probabilities"].values(),reverse=True)
        passes=r["prediction"] in eligible and r["probabilities"][r["prediction"]]>=threshold and ranked[0]-ranked[1]>=margin
        selector_passes=passes
        reason="probability selector rejected"
        if passes and a.source_guards:
            from kev_source_guards import accepted_prediction
            doc=json.loads(Path(r["path"]).read_text(encoding="utf-8"))
            passes,reason=accepted_prediction(doc,r,guard_cfg)
        if passes:
            accepted.append(r)
        elif a.source_guards and selector_passes:
            guard_rejections.append({"id":r["case_id"],"prediction":r["prediction"],"reason":reason})
    correct=sum(r["prediction"]==r["expected"] for r in accepted)
    summary={"model":a.model,"model_fingerprint":mf,"cases":len(rows),"errors":sum(r.get("status")!="ok" for r in rows),"scored":sum(r.get("status")=="ok" for r in rows),"evaluated":len(ok),"threshold":threshold,"minimum_margin":margin,"eligible_choices":eligible,"source_guards":a.source_guards,"guard_rejections":guard_rejections,"accepted":len(accepted),"coverage":len(accepted)/len(ok) if ok else None,"accepted_correct":correct,"accepted_precision":correct/len(accepted) if accepted else None,"accuracy_all":sum(r["prediction"]==r["expected"] for r in ok)/len(ok) if ok else None,"confusions":[{"id":r["case_id"],"expected":r["expected"],"predicted":r["prediction"],"p":r["probabilities"][r["prediction"]]} for r in ok if r["prediction"]!=r["expected"]]}
    if a.source_guards:
        from kev_source_guards import __file__ as guard_path
        summary["source_guard_policy"]="source-attribution-v1"
        summary["source_guard_sha256"]=hashlib.sha256(Path(guard_path).read_bytes()).hexdigest()
    Path(str(out)+".summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n");print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
