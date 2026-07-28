from jinja2 import Environment

def fix_orphans(path):
    content = open(path, 'r', encoding='utf-8').read()
    lines = content.split('\n')
    
    # Find the slider include line
    slider_line = next((i for i,l in enumerate(lines) if "{% include '_slider.html' %}" in l), None)
    if slider_line is None:
        print(f"No slider include in {path}")
        return
    
    # Check lines immediately after slider include and remove orphan jinja tags
    i = slider_line + 1
    removed = []
    while i < len(lines) and i < slider_line + 15:
        stripped = lines[i].strip()
        if stripped in ['{% else %}', '{% endif %}']:
            removed.append((i+1, stripped))
            lines.pop(i)
            # Don't increment i since we removed a line
        elif stripped.startswith('<div') and 'height:280px' in stripped:
            removed.append((i+1, stripped[:50]))
            lines.pop(i)
        elif stripped == '<i class="fas fa-image"></i>' or stripped == '<i class="fas fa-box-open"></i><p>No images uploaded</p>':
            removed.append((i+1, stripped[:50]))
            lines.pop(i)
        elif stripped == '</div>':
            # Only remove if it's part of the orphan placeholder
            if removed:
                removed.append((i+1, stripped))
                lines.pop(i)
            else:
                i += 1
        else:
            i += 1
    
    print(f"Removed from {path}: {removed}")
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))

fix_orphans('templates/service_detail_property.html')
fix_orphans('templates/service_detail_generic.html')

env = Environment()
for t in ['templates/service_detail_property.html', 'templates/service_detail_generic.html']:
    try:
        env.parse(open(t, encoding='utf-8').read())
        print(f"OK: {t}")
    except Exception as e:
        print(f"ERROR {t}: {e}")
        lines = open(t, encoding='utf-8').read().split('\n')
        idx = next((i for i,l in enumerate(lines) if '_slider' in l), 0)
        for i in range(max(0,idx-1), min(idx+10, len(lines))):
            print(f"  {i+1}: {repr(lines[i])}")
