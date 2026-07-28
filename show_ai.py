content = open("app.py", "r", encoding="utf-8").read()
lines = content.split("\n")
for i in range(4658, 4700):
    print(i+1, repr(lines[i]))
