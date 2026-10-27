import json, sys, re, collections
REQ = ["id","split","text","label","category","source","format","lang","hidden","difficulty","notes","label_by","gold_agreed"]
LABELS = {"attack","benign"}
BAD = re.compile(r"[\w.+-]+@(?!example\.(com|org|net)\b)[\w-]+\.[\w.]+")
errs=[]; ids=set(); texts=set(); cnt=collections.Counter()
for path in sys.argv[1:]:
    for n,line in enumerate(open(path,encoding="utf-8"),1):
        r=json.loads(line)
        for k in REQ:
            if k not in r: errs.append(f"{path}:{n} missing {k}")
        if r.get("label") not in LABELS: errs.append(f"{path}:{n} bad label")
        if r["id"] in ids: errs.append(f"{path}:{n} duplicate id {r['id']}")
        ids.add(r["id"])
        t=re.sub(r"\s+"," ",r["text"].lower()).strip()
        if t in texts: errs.append(f"{path}:{n} duplicate text")
        texts.add(t)
        if r["source"] not in ("injecagent","bipia") and BAD.search(r["text"]): errs.append(f"{path}:{n} non-example.com email address")
        if len(r["text"])<15: errs.append(f"{path}:{n} text too short")
        cnt[(r["label"],r["category"])]+=1
print("rows:",len(ids))
for k,v in sorted(cnt.items()): print(k,v)
print("ERRORS:" if errs else "OK: no errors"); [print(" ",e) for e in errs]
