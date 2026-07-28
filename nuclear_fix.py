import re

fixes = {
    'templates/service_detail_product.html': '    <div class="pd-layout">',
    'templates/service_detail_property.html': '<div class="re-page">',
    'templates/service_detail_generic.html': '  <div class="gd-layout">',
}

for path, restart_marker in fixes.items():
    content = open(path, 'r', encoding='utf-8').read()
    
    # Find the slider include position
    include_pos = content.find("{% include '_slider.html' %}")
    if include_pos == -1:
        print(f"No include found in {path}")
        continue
    
    # Find end of the include line
    include_end = content.find('\n', include_pos) + 1
    
    # Find where the next real content section starts after the old slider mess
    # Look for the next major section marker after the slider
    next_section_markers = [
        '<!-- Product Details -->',
        '<!-- Property Details -->',
        '<!-- Service Details -->',
        '<div class="pd-details',
        '<div class="re-body',
        '<div class="gd-details',
        '<div class="pd-section">',
        '<!-- Details -->',
        '<div class="re-info',
        '    <div class="pd-right',
        '  <div class="gd-right',
        '  <div class="re-right',
    ]
    
    # Find the end of slider junk - look for closing of old slider section
    # Everything between include and the next real section is junk
    after_include = content[include_end:]
    
    # Find first occurrence of a non-slider div
    junk_end = None
    for marker in next_section_markers:
        pos = after_include.find(marker)
        if pos != -1:
            if junk_end is None or pos < junk_end:
                junk_end = pos
    
    if junk_end is None:
        # Try to find end by looking for content that's clearly not slider
        # Find first line that doesn't contain slider-related content
        lines = after_include.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not any(x in stripped for x in [
                'img-slide', 'img-slider', 'fh-slide', 'fh-slider',
                'endfor', 'endfor', '{% for ', '{% if ', '{% endif %}',
                'imgSlide', 'imgGoTo', 'video controls', 'source src',
                '</video>', 'img src', 'img-thumb', 'slider-counter',
                'slider-prev', 'slider-next', 'slider-thumbs',
                'loop.first', 'loop.index', 'video_list', 'image_list',
                '</div>', '<div class="img', '<button class="img',
            ]):
                junk_end = sum(len(l)+1 for l in lines[:i])
                break
    
    if junk_end is not None:
        new_content = content[:include_end] + after_include[junk_end:]
        open(path, 'w', encoding='utf-8').write(new_content)
        print(f"Fixed {path} - removed {junk_end} chars of junk")
    else:
        print(f"Could not find junk end in {path}")

# Verify
from jinja2 import Environment
env = Environment()
for path in fixes:
    try:
        env.parse(open(path, encoding='utf-8').read())
        print(f"OK: {path}")
    except Exception as e:
        print(f"ERROR {path}: {e}")
        # Show problem area
        content = open(path, encoding='utf-8').read()
        lines = content.split('\n')
        include_line = next((i for i,l in enumerate(lines) if '_slider.html' in l), 0)
        for i in range(include_line, min(include_line+15, len(lines))):
            print(f"  {i+1}: {lines[i]}")
