from jinja2 import Environment

# Fix service_detail_property.html - remove orphan else/endif after include
content = open('templates/service_detail_property.html', 'r', encoding='utf-8').read()
content = content.replace(
    "{% include '_slider.html' %}\n{% else %}\n<div style=\"width:100%;height:280px;background:#111;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#444;font-size:3rem;margin-bottom:1rem\">\n  <i class=\"fas fa-image\"></i>\n</div>\n{% endif %}",
    "{% include '_slider.html' %}"
)
open('templates/service_detail_property.html', 'w', encoding='utf-8').write(content)
print("fixed property")

# Fix service_detail_generic.html
content = open('templates/service_detail_generic.html', 'r', encoding='utf-8').read()
content = content.replace(
    "{% include '_slider.html' %}\n{% else %}\n<div class=\"gd-img-ph\"><i class=\"fas fa-box-open\"></i><p>No images uploaded</p></div>\n{% endif %}",
    "{% include '_slider.html' %}"
)
open('templates/service_detail_generic.html', 'w', encoding='utf-8').write(content)
print("fixed generic")

# Fix service_detail_product.html - remove orphan endif after include
content = open('templates/service_detail_product.html', 'r', encoding='utf-8').read()
# Find the include and remove the orphan endif that follows the video section
import re
content = re.sub(
    r"(\{%\s*include '_slider\.html'\s*%\})\s*(<div[^>]*>.*?</div>\s*\{%\s*endif\s*%\})",
    r"\1",
    content, flags=re.DOTALL, count=1
)
open('templates/service_detail_product.html', 'w', encoding='utf-8').write(content)
print("fixed product")

# Verify all
env = Environment()
for t in ['templates/service_detail_product.html','templates/service_detail_property.html','templates/service_detail_generic.html']:
    try:
        env.parse(open(t, encoding='utf-8').read())
        print(f"OK: {t}")
    except Exception as e:
        print(f"ERROR {t}: {e}")
        content = open(t, encoding='utf-8').read()
        lines = content.split('\n')
        idx = next((i for i,l in enumerate(lines) if '_slider.html' in l), 0)
        for i in range(idx, min(idx+10, len(lines))):
            print(f"  {i+1}: {lines[i]}")
