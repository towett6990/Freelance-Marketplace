content = open("app.py", "r", encoding="utf-8").read()
lines = content.split("\n")
print("lines 2824-2834:")
for i in range(2823, 2834):
    print(i+1, repr(lines[i]))
