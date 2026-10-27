"""Freeze the dev/test split. Run from the data/ folder:  python make_split.py
Deterministic: same raw files + same seed -> same split and same hashes."""
import json, glob, random, hashlib, collections, sys
SEED = 20261017
FILES = ["raw/tricky_benign_v1.jsonl","raw/attacks_v1.jsonl","raw/normal_v1.jsonl"]
rows=[]
for p in FILES:
    with open(p,encoding="utf-8") as f:           # universal newlines: CRLF/LF both fine
        rows += [json.loads(l) for l in f if l.strip()]
ids=[r["id"] for r in rows]; assert len(ids)==len(set(ids)), "duplicate ids"
groups=collections.defaultdict(list)
for r in sorted(rows,key=lambda r:r["id"]): groups[(r["label"],r["category"])].append(r)
rng=random.Random(SEED); dev=[]; test=[]
for key in sorted(groups):
    g=groups[key][:]; rng.shuffle(g); k=(len(g)+1)//2      # dev gets the extra row when odd
    dev+=g[:k]; test+=g[k:]
def dump(path,rs,name):
    rs=sorted(rs,key=lambda r:r["id"])
    for r in rs: r["split"]=name
    data="".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rs)
    with open(path,"w",encoding="utf-8",newline="\n") as f: f.write(data)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
h_dev=dump("dev.jsonl",dev,"dev"); h_test=dump("test.jsonl",test,"test")
def cnt(rs): return dict(collections.Counter(r["label"] for r in rs))
man={"seed":SEED,"method":"stratified 50/50 by (label, category); dev gets extra row when odd",
     "dev":{"rows":len(dev),"labels":cnt(dev),"sha256":h_dev},
     "test":{"rows":len(test),"labels":cnt(test),"sha256":h_test}}
json.dump(man,open("SPLIT_MANIFEST.json","w"),indent=2)
print(json.dumps(man,indent=2))
