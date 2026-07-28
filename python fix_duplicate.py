content = open('app.py', encoding='utf-8', errors='ignore').read()
lines = content.split('\n')

# Find def upload_id line
upload_id_line = next((i for i,l in enumerate(lines) if 'def upload_id' in l), None)
if upload_id_line is None:
    print("def upload_id not found!")
    exit()

# Walk back to find the @app.route decorator
route_start = upload_id_line
while route_start > 0 and not lines[route_start].startswith('@app.route'):
    route_start -= 1

# Walk forward to find end of function (next @app.route or top-level def)
route_end = upload_id_line + 1
while route_end < len(lines):
    stripped = lines[route_end]
    if stripped.startswith('@app.route') or (stripped.startswith('def ') and not stripped.startswith('    ')):
        break
    route_end += 1

print(f"Removing lines {route_start+1} to {route_end}: {lines[route_start][:60]}")
new_lines = lines[:route_start] + lines[route_end:]
open('app.py', 'w', encoding='utf-8').write('\n'.join(new_lines))
print("Done! Now run: python app.py")