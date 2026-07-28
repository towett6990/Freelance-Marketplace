import re, os

for root, dirs, files in os.walk("templates"):
    for f in files:
        if not f.endswith(".html"): continue
        path = os.path.join(root, f)
        content = open(path, "r", encoding="utf-8").read()
        for i, line in enumerate(content.split("\n"), 1):
            for m in re.finditer(r"\{\{(.*?)\}\}", line):
                expr = m.group(1)
                if expr.count(")") > expr.count("("):
                    print(f"{path}:{i}: {line.strip()[:100]}")
