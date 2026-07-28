content = open("models.py", "r", encoding="utf-8").read()
lines = content.split("\n")
print("lines 570-580:")
for i in range(569, 580):
    print(i+1, repr(lines[i]))
