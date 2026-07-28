import shutil
import os

# Copy first
source = r"C:\Freelance_marketplace\app.py"
dest = "app.py"
shutil.copy2(source, dest)

# Then read
with open(dest, 'r', encoding='utf-8') as f:
    content = f.read()

# Write result
with open('final_result.txt', 'w', encoding='utf-8') as f:
    f.write(f"File copied successfully\n")
    f.write(f"Content length: {len(content)} chars\n")
    f.write(f"Lines: {len(content.split(chr(10)))}\n")
    f.write("First 500 chars:\n")
    f.write(content[:500])

print("DONE - Check final_result.txt")