# Fix packages_manage.html line 42
content = open("templates/packages_manage.html", "r", encoding="utf-8").read()
lines = content.split("\n")
print("lines 40-45:")
for i in range(39, 45):
    print(i+1, repr(lines[i]))
