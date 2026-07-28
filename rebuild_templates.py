import re

def clean_template(path, title_line):
    """Rebuild template with clean title block"""
    content = open(path, 'r', encoding='utf-8').read()
    
    # Find where {% block content %} starts (after all the mess)
    block_match = re.search(r'\{%[-\s]*block content[-\s]*%\}', content)
    if not block_match:
        print(f"ERROR: no block content in {path}")
        return
    
    # Get everything from block content onwards
    rest = content[block_match.start():]
    
    # Remove any old slider JS/CSS that got injected into wrong places
    rest = re.sub(r'<style>\s*\.img-slider.*?</style>', '', rest, flags=re.DOTALL)
    rest = re.sub(r'<style>\s*\.fh-slider.*?</style>', '', rest, flags=re.DOTALL)
    rest = re.sub(r'<script>.*?window\.(imgSlide|imgGoTo|fhNext|fhPrev).*?</script>', '', rest, flags=re.DOTALL)
    
    # Replace old image sections with clean include
    rest = re.sub(
        r'\{%[-\s]*if service\.image_list or service\.video_list[-\s]*%\}.*?\{%[-\s]*endif[-\s]*%\}',
        "{% include '_slider.html' %}",
        rest, flags=re.DOTALL, count=1
    )
    
    # Also replace old .re-hero-img, .gallery-main-wrap etc
    rest = re.sub(
        r'<div class="re-hero-img[^"]*"[^>]*>.*?</div>',
        "{% include '_slider.html' %}",
        rest, flags=re.DOTALL, count=1
    )
    
    # Build clean template
    new_content = f"""{{% extends 'base.html' %}}
{{% block title %}}{title_line}{{% endblock %}}
{{% include '_slider_assets.html' %}}
{rest}"""
    
    open(path, 'w', encoding='utf-8').write(new_content)
    print(f"REBUILT: {path}")

# Get current titles from templates
import re

for tmpl, title in [
    ('templates/service_detail_property.html', '{{ service.title }} — Property'),
    ('templates/service_detail_product.html', '{{ service.title }} — FreelancingHub'),
    ('templates/service_detail_generic.html', '{{ service.title }} — FreelancingHub'),
    ('templates/service_detail_freelancer.html', '{{ service.title }} — FreelancingHub'),
]:
    clean_template(tmpl, title)

print("done")
