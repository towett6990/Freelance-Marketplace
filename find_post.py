content = open("app.py", "r", encoding="utf-8").read()
lines = content.split("\n")
for i, line in enumerate(lines, 1):
    if "Service posted successfully" in line:
        print(f"Found at line {i}")
        for j in range(i-5, i+5):
            print(j+1, repr(lines[j]))
