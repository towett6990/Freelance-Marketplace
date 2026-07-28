content = open("templates/chat.html", "r", encoding="utf-8").read()
lines = content.split("\n")
for i, line in enumerate(lines, 1):
    if "msg.content" in line and "lower" in line:
        print(i, repr(line.strip()))
