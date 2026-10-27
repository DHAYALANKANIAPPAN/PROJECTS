"""Build a seeded slice of public injection benchmarks in our row format.
Usage (from data/):  python make_benchmark_slice.py <path-to-InjecAgent> <path-to-BIPIA>
Both repos are MIT licensed. Only attack strings / tool-response templates are used,
never BIPIA's email/qa/table contexts (they derive from other datasets with other licenses)."""
import json, random, sys, subprocess
SEED = 20261017
ia_dir, bp_dir = sys.argv[1], sys.argv[2]
def commit(d): return subprocess.run(["git","-C",d,"rev-parse","HEAD"],capture_output=True,text=True).stdout.strip()
rng = random.Random(SEED); rows=[]
def add(src,fmt,text,label,cat,notes):
    rows.append(dict(id=f"bm-{len(rows)+1:03d}",split="benchmark",text=text,label=label,category=cat,
        source=src,format=fmt,lang="en",hidden=False,difficulty="medium",notes=notes,
        label_by=["upstream" if label=="attack" else "akshiya"],gold_agreed=True if label=="attack" else None))

# --- InjecAgent: 15 direct-harm + 15 data-stealing test cases, seeded ---
PH="<Attacker Instruction>"
NEUTRAL=["Works well and arrived on time. Would recommend.","Good value for the price. Five stars.",
         "Decent quality, packaging was a bit damaged.","Exactly as described. Fast delivery."]
picked=[]
for fn,n in (("test_cases_dh_base.json",15),("test_cases_ds_base.json",15)):
    cases=json.load(open(f"{ia_dir}/data/{fn}"))
    cases=[c for c in cases if PH in c["Tool Response Template"]]
    for c in rng.sample(cases,n): picked.append((fn,c))
for fn,c in picked:
    add("injecagent","tool_output",c["Tool Response Template"].replace(PH,c["Attacker Instruction"]),
        "attack","tool_output","InjecAgent "+fn+"; type="+str(c.get("Attack Type")))
seen=set(r["text"] for r in rows); made=0
for fn,c in picked:                      # paired benign controls: same template, neutral content, unique texts
    if made==15: break
    opts=NEUTRAL[:]; rng.shuffle(opts)
    for o in opts:
        t=c["Tool Response Template"].replace(PH,o)
        if t not in seen:
            seen.add(t); add("injecagent","tool_output",t,"benign","normal","paired control for an InjecAgent template (our own neutral filler)"); made+=1; break

# --- BIPIA: 20 attack strings from text_attack_test.json in our own neutral carriers ---
atk=json.load(open(f"{bp_dir}/benchmark/text_attack_test.json"))
pool=sorted((k,s) for k,v in atk.items() for s in v)
CARRIERS=["Thanks for your message. Our office is open Monday to Friday and we will reply within two business days.\n\n{A}\n\nBest regards, the front desk.",
          "Meeting notes: the team reviewed the roadmap and agreed on next steps for the quarter.\n\n{A}\n\nNext meeting is on Thursday.",
          "Product update: version 3.2 adds dark mode and faster sync.\n\n{A}\n\nSee the full changelog on our website.",
          "Weather report for the weekend: mild temperatures and light winds across the region.\n\n{A}\n\nHave a pleasant weekend."]
for k,s in rng.sample(pool,20):
    add("bipia","email",rng.choice(CARRIERS).replace("{A}",s),"attack","reworded","BIPIA text_attack_test.json ("+k+"), embedded in our neutral carrier")

with open("benchmark_slice.jsonl","w",encoding="utf-8",newline="\n") as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
json.dump({"seed":SEED,"injecagent_commit":commit(ia_dir),"bipia_commit":commit(bp_dir),
           "licenses":{"injecagent":"MIT (LICENCE file, (c) 2023 Qiusi Zhan)","bipia":"MIT (LICENSE file, (c) Microsoft Corporation)"},
           "rows":len(rows)},open("BENCHMARK_MANIFEST.json","w"),indent=2)
print(len(rows),"rows;",sum(r["label"]=="attack" for r in rows),"attacks")
