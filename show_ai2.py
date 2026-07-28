content = open("app.py", "r", encoding="utf-8").read()
lines = content.split("\n")
for i in range(4768, 4810):
    print(i+1, repr(lines[i]))
