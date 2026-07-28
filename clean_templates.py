# Fix product - remove orphan endif after video section
content = open('templates/service_detail_product.html', 'r', encoding='utf-8').read()
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Remove orphan endif that follows the video section after slider include
    if line.strip() == '{% endif %}' and i > 0:
        # Check if previous non-empty line is closing a div (not an if block)
        prev = new_lines[-1].strip() if new_lines else ''
        if '</div>' in prev or prev == '}':
            # Check if this endif has no matching if above it in recent context
            recent = '\n'.join(l.strip() for l in new_lines[-20:] if l.strip())
            if_count = recent.count('{% if ') + recent.count('{% elif ')
            endif_count = recent.count('{% endif %}')
            if endif_count >= if_count:
                i += 1
                continue
    new_lines.append(line)
    i += 1
open('templates/service_detail_product.html', 'w', encoding='utf-8').write('\n'.join(new_lines))
print("processed product")

# Fix property and generic - remove orphan else/endif after include
for path in ['templates/service_detail_property.html', 'templates/service_detail_generic.html']:
    content = open(path, 'r', encoding='utf-8').read()
    lines = content.split('\n')
    new_lines = []
    skip_orphan = False
    for line in lines:
        if skip_orphan:
            if line.strip() == '{% endif %}':
                skip_orphan = False
                continue
            if line.strip() in ['{% else %}'] or line.strip().startswith('<div') or line.strip() == '':
                continue
        if "{% include '_slider.html' %}" in line:
            new_lines.append(line)
            skip_orphan = True
            continue
        new_lines.append(line)
    open(path, 'w', encoding='utf-8').write('\n'.join(new_lines))
    print(f"processed {path}")

# Verify all
from jinja2 import Environment
env = Environment()
for t in ['templates/service_detail_product.html', 'templates/service_detail_property.html', 'templates/service_detail_generic.html']:
    try:
        env.parse(open(t, encoding='utf-8').read())
        print(f"OK: {t}")
    except Exception as e:
        print(f"ERROR {t}: {e}")
        lines = open(t, encoding='utf-8').read().split('\n')
        idx = next((i for i,l in enumerate(lines) if '_slider' in l), 0)
        for i in range(max(0,idx-2), min(idx+8, len(lines))):
            print(f"  {i+1}: {lines[i]}")
