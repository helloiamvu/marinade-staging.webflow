#!/usr/bin/env python3
"""Generate static blog HTML pages from CMS CSV export."""

import csv
import os
import html
from datetime import datetime
import re

CSV_PATH = '/data/media/inbound/file_60---5e98cad4-21f0-4509-9b3e-0d843160a5cb.csv'
TEMPLATE_PATH = 'detail_blog.html'
OUTPUT_DIR = 'blog'
SITE_URL = 'https://marinade.finance'

def parse_date(date_str):
    """Parse the CSV date string and return a datetime object."""
    if not date_str:
        return None
    # Format: "Thu Jun 05 2025 00:00:00 GMT+0000 (Coordinated Universal Time)"
    try:
        clean = re.sub(r'\s*\(.*\)', '', date_str).strip()
        clean = re.sub(r'GMT([+-]\d{4})', r'\1', clean)
        return datetime.strptime(clean, '%a %b %d %Y %H:%M:%S %z')
    except:
        try:
            clean = re.sub(r'\s*\(.*\)', '', date_str).strip()
            clean = re.sub(r'GMT([+-]\d{4})', r'+0000', clean)
            return datetime.strptime(clean, '%a %b %d %Y %H:%M:%S %z')
        except:
            return None

def format_date(dt):
    """Format datetime as 'June 5, 2025'."""
    if not dt:
        return ''
    return dt.strftime('%B %-d, %Y')

def read_template():
    """Read and split the template into head, nav, and footer sections."""
    with open(TEMPLATE_PATH, 'r') as f:
        return f.read()

def extract_section(template, start_marker, end_marker=None):
    """Extract section from template between markers."""
    start = template.find(start_marker)
    if start == -1:
        return ''
    if end_marker:
        end = template.find(end_marker, start + len(start_marker))
        if end == -1:
            return template[start:]
        return template[start:end + len(end_marker)]
    return template[start:]

def build_head(title, description, thumbnail, slug):
    """Build the <head> section with proper meta tags."""
    return f'''<head>
  <meta charset="utf-8">
  <title>{html.escape(title)} | Marinade Blog</title>
  <meta content="{html.escape(description or '')}" name="description">
  <meta content="{html.escape(title)}" property="og:title">
  <meta content="{html.escape(description or '')}" property="og:description">
  <meta content="{html.escape(thumbnail or '')}" property="og:image">
  <meta content="{html.escape(title)}" property="twitter:title">
  <meta content="{html.escape(description or '')}" property="twitter:description">
  <meta content="{html.escape(thumbnail or '')}" property="twitter:image">
  <meta property="og:type" content="article">
  <meta content="summary_large_image" name="twitter:card">
  <meta content="width=device-width, initial-scale=1" name="viewport">
  <link rel="canonical" href="{SITE_URL}/blog/{slug}.html">
  <link href="../css/normalize.css" rel="stylesheet" type="text/css">
  <link href="../css/webflow.css" rel="stylesheet" type="text/css">
  <link href="../css/marinade-staging.webflow.css" rel="stylesheet" type="text/css">
  <link href="https://fonts.googleapis.com" rel="preconnect">
  <link href="https://fonts.gstatic.com" rel="preconnect" crossorigin="anonymous">
  <script src="https://ajax.googleapis.com/ajax/libs/webfont/1.6.26/webfont.js" type="text/javascript"></script>
  <script type="text/javascript">WebFont.load({{  google: {{    families: ["PT Serif:400,400italic,700,700italic","DM Mono:300,400,500,600,700","DM Sans:300,400,500,600,700","PT Serif Caption:300,400,500,600,700"]  }}}});</script>
  <script type="text/javascript">!function(o,c){{var n=c.documentElement,t=" w-mod-";n.className+=t+"js",("ontouchstart"in o||o.DocumentTouch&&c instanceof DocumentTouch)&&(n.className+=t+"touch")}}(window,document);</script>
  <link href="../images/favicon.ico" rel="shortcut icon" type="image/x-icon">
  <link href="../images/webclip.ico" rel="apple-touch-icon">
</head>'''

def get_nav_html(template):
    """Extract nav from template and fix paths."""
    # Find the navbar
    start = template.find('<div data-animation="default" class="navbar_wrapper')
    if start == -1:
        return ''
    # Find the closing of nav section - it ends before <main>
    main_start = template.find('<main', start)
    if main_start == -1:
        main_start = template.find('<section class="section_article_hero"', start)
    nav = template[start:main_start] if main_start > start else ''
    # Fix relative paths
    nav = fix_paths(nav)
    return nav

def get_footer_html(template):
    """Extract footer and scripts from template."""
    start = template.find('<section data-w-id="06eed885-e3f4-9890-a863-4367c47818be" class="section_subscription">')
    if start == -1:
        start = template.find('<section data-w-id="48227bf5-72b8-226a-8260-2abb46bcbe9b" class="footer_component">')
    if start == -1:
        return ''
    footer = template[start:]
    footer = fix_paths(footer)
    return footer

def fix_paths(content):
    """Fix relative paths for blog/ subdirectory."""
    # Fix href and src paths that are relative (not starting with http, //, #, or javascript:)
    content = re.sub(r'href="((?!https?://|//|#|javascript:|mailto:)[^"]*\.(?:html|css|js|ico|png|jpg|svg|webp))"', 
                     lambda m: f'href="../{m.group(1)}"' if not m.group(1).startswith('../') else m.group(0), content)
    content = re.sub(r'src="((?!https?://|//|data:)[^"]*\.(?:js|png|jpg|svg|webp|gif|ico))"',
                     lambda m: f'src="../{m.group(1)}"' if not m.group(1).startswith('../') else m.group(0), content)
    content = re.sub(r'srcset="([^"]*)"', lambda m: fix_srcset(m.group(1)), content)
    return content

def fix_srcset(srcset):
    """Fix srcset paths."""
    parts = srcset.split(',')
    fixed = []
    for part in parts:
        part = part.strip()
        if part and not part.startswith('http') and not part.startswith('//') and not part.startswith('../'):
            # Find the URL part (before the size descriptor)
            match = re.match(r'(\S+)(.*)', part)
            if match:
                part = f'../{match.group(1)}{match.group(2)}'
        fixed.append(part)
    return f'srcset="{", ".join(fixed)}"'

def generate_article_page(article, template, nav_html, footer_html):
    """Generate a single article page."""
    title = article['Title'].strip()
    slug = article['Slug'].strip()
    category = article.get('Category', '').strip()
    date_str = article.get('Date', '')
    dt = parse_date(date_str)
    formatted_date = format_date(dt)
    read_time = article.get('Read Time', '').strip()
    description = article.get('Description', '').strip()
    content_html = article.get('Content', '')
    thumbnail = article.get('Thumbnail', '').strip()

    page = f'''<!DOCTYPE html>
<html lang="en">
{build_head(title, description, thumbnail, slug)}
<body>
  <div class="page_code-wrapper">
    <div class="global-styles w-embed">
      <style>
        html {{ background-color: white; }}
        body {{
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          text-rendering: geometricPrecision;
        }}
      </style>
    </div>
    {nav_html}
    <main class="main-wrapper">
      <section class="section_article_hero">
        <div class="padding-section-large is-article">
          <div class="page-padding">
            <div class="container-large">
              <div class="article_hero-grid">
                <div class="article_hero-content">
                  <div class="margin-bottom margin-small">
                    <div class="news_meta is-article">
                      <div class="news_category">{html.escape(category)}</div>
                      <div class="news_meta-divider"></div>
                      <div class="news_date">{html.escape(formatted_date)}</div>
                      <div class="news_meta-divider"></div>
                      <div class="news_read-time">{html.escape(read_time)}</div>
                    </div>
                  </div>
                  <h1 class="heading-style-h2">{html.escape(title)}</h1>
                </div>
                <div class="article_thumbnail-wrapper">
                  {"<img src='" + html.escape(thumbnail) + "' loading='lazy' alt='" + html.escape(title) + "' class='news_thumbnail-image'>" if thumbnail else ""}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section class="section_article_text">
        <div class="page-padding">
          <div class="container-large">
            <div class="article_text-container">
              <div class="text_component is-article">
                <div class="text-rich-text w-richtext">{content_html}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
    {footer_html}
  </div>
  <script src="https://d3e54v103j8qbb.cloudfront.net/js/jquery-3.5.1.min.dc5e7f18c8.js?site=664c7876d83b34499b5688a0" type="text/javascript" integrity="sha256-9/aliU8dGd2tb6OSsuzixeV4y/faTqgFtohetphbbj0=" crossorigin="anonymous"></script>
  <script src="../js/webflow.js" type="text/javascript"></script>
</body>
</html>'''
    return page

def generate_index_page(articles, nav_html, footer_html):
    """Generate the blog index page."""
    # Sort by date, newest first
    def sort_key(a):
        dt = parse_date(a.get('Date', ''))
        return dt or datetime.min.replace(tzinfo=None)
    
    # For sorting with timezone awareness
    from datetime import timezone
    def sort_key_tz(a):
        dt = parse_date(a.get('Date', ''))
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt
    
    articles_sorted = sorted(articles, key=sort_key_tz, reverse=True)
    
    # Get unique categories
    categories = sorted(set(a.get('Category', '').strip() for a in articles if a.get('Category', '').strip()))
    
    # Build category filter links
    cat_links = '<a href="#" class="r_button is-small is-active" data-category="all" onclick="filterCategory(\'all\', this); return false;">All</a>\n'
    for cat in categories:
        cat_links += f'<a href="#" class="r_button is-small" data-category="{html.escape(cat)}" onclick="filterCategory(\'{html.escape(cat)}\', this); return false;">{html.escape(cat.replace("-", " ").title())}</a>\n'
    
    # Build article cards
    cards = ''
    for a in articles_sorted:
        title = a['Title'].strip()
        slug = a['Slug'].strip()
        category = a.get('Category', '').strip()
        dt = parse_date(a.get('Date', ''))
        formatted_date = format_date(dt)
        description = a.get('Description', '').strip()
        thumbnail = a.get('Thumbnail', '').strip()
        read_time = a.get('Read Time', '').strip()
        
        cards += f'''
        <a href="{slug}.html" class="news_card-link w-inline-block" data-category="{html.escape(category)}">
          <div class="news_card">
            <div class="news_card-image-wrapper">
              {"<img src='" + html.escape(thumbnail) + "' loading='lazy' alt='" + html.escape(title) + "' class='news_card-image'>" if thumbnail else ""}
            </div>
            <div class="news_card-content">
              <div class="news_meta">
                <div class="news_category">{html.escape(category)}</div>
                <div class="news_meta-divider"></div>
                <div class="news_date">{html.escape(formatted_date)}</div>
                <div class="news_meta-divider"></div>
                <div class="news_read-time">{html.escape(read_time)}</div>
              </div>
              <h3 class="heading-style-h5">{html.escape(title)}</h3>
              <p class="text-size-regular text-color-secondary text-style-3lines">{html.escape(description)}</p>
            </div>
          </div>
        </a>'''
    
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Blog | Marinade</title>
  <meta content="Latest news, updates, and insights from Marinade Finance" name="description">
  <meta content="Blog | Marinade" property="og:title">
  <meta content="Latest news, updates, and insights from Marinade Finance" property="og:description">
  <meta property="og:type" content="website">
  <meta content="summary_large_image" name="twitter:card">
  <meta content="width=device-width, initial-scale=1" name="viewport">
  <link href="../css/normalize.css" rel="stylesheet" type="text/css">
  <link href="../css/webflow.css" rel="stylesheet" type="text/css">
  <link href="../css/marinade-staging.webflow.css" rel="stylesheet" type="text/css">
  <link href="https://fonts.googleapis.com" rel="preconnect">
  <link href="https://fonts.gstatic.com" rel="preconnect" crossorigin="anonymous">
  <script src="https://ajax.googleapis.com/ajax/libs/webfont/1.6.26/webfont.js" type="text/javascript"></script>
  <script type="text/javascript">WebFont.load({{  google: {{    families: ["PT Serif:400,400italic,700,700italic","DM Mono:300,400,500,600,700","DM Sans:300,400,500,600,700","PT Serif Caption:300,400,500,600,700"]  }}}});</script>
  <script type="text/javascript">!function(o,c){{var n=c.documentElement,t=" w-mod-";n.className+=t+"js",("ontouchstart"in o||o.DocumentTouch&&c instanceof DocumentTouch)&&(n.className+=t+"touch")}}(window,document);</script>
  <link href="../images/favicon.ico" rel="shortcut icon" type="image/x-icon">
  <link href="../images/webclip.ico" rel="apple-touch-icon">
  <style>
    .blog-filter-bar {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .blog-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; }}
    @media screen and (max-width: 991px) {{ .blog-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media screen and (max-width: 479px) {{ .blog-grid {{ grid-template-columns: 1fr; }} }}
    .news_card {{ border-radius: 1rem; overflow: hidden; background: #f7f7f7; height: 100%; }}
    .news_card-image-wrapper {{ aspect-ratio: 16/9; overflow: hidden; }}
    .news_card-image {{ width: 100%; height: 100%; object-fit: cover; }}
    .news_card-content {{ padding: 1.5rem; }}
    .news_card-link {{ text-decoration: none; color: inherit; }}
    .news_card-link:hover .news_card {{ box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .r_button.is-small {{ padding: 0.5rem 1rem; border-radius: 2rem; border: 1px solid #ddd; background: white; cursor: pointer; font-size: 0.875rem; text-decoration: none; color: #151A1A; }}
    .r_button.is-small.is-active {{ background: #151A1A; color: white; border-color: #151A1A; }}
    .blog-hidden {{ display: none !important; }}
  </style>
</head>
<body>
  <div class="page_code-wrapper">
    <div class="global-styles w-embed">
      <style>
        html {{ background-color: white; }}
        body {{
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          text-rendering: geometricPrecision;
        }}
      </style>
    </div>
    {nav_html}
    <main class="main-wrapper">
      <section class="section_blog-header">
        <div class="padding-section-large">
          <div class="page-padding">
            <div class="container-large">
              <div class="margin-bottom margin-large">
                <h1 class="heading-style-h1">Blog</h1>
              </div>
              <div class="blog-filter-bar">
                {cat_links}
              </div>
              <div class="blog-grid" id="blogGrid">
                {cards}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
    {footer_html}
  </div>
  <script src="https://d3e54v103j8qbb.cloudfront.net/js/jquery-3.5.1.min.dc5e7f18c8.js?site=664c7876d83b34499b5688a0" type="text/javascript" integrity="sha256-9/aliU8dGd2tb6OSsuzixeV4y/faTqgFtohetphbbj0=" crossorigin="anonymous"></script>
  <script src="../js/webflow.js" type="text/javascript"></script>
  <script>
    function filterCategory(cat, btn) {{
      // Update active button
      document.querySelectorAll('.blog-filter-bar .r_button').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      // Filter cards
      document.querySelectorAll('#blogGrid .news_card-link').forEach(card => {{
        if (cat === 'all' || card.getAttribute('data-category') === cat) {{
          card.classList.remove('blog-hidden');
        }} else {{
          card.classList.add('blog-hidden');
        }}
      }});
    }}
  </script>
</body>
</html>'''
    return page

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Read CSV
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_articles = list(reader)
    
    # Filter published
    published = [a for a in all_articles if a.get('Draft', '').lower() != 'true' and a.get('Archived', '').lower() != 'true']
    print(f'Total articles: {len(all_articles)}, Published: {len(published)}')
    
    # Read template and extract nav/footer
    template = read_template()
    nav_html = get_nav_html(template)
    footer_html = get_footer_html(template)
    
    # Generate individual pages
    for article in published:
        slug = article['Slug'].strip()
        if not slug:
            continue
        page_html = generate_article_page(article, template, nav_html, footer_html)
        filepath = os.path.join(OUTPUT_DIR, f'{slug}.html')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(page_html)
    
    print(f'Generated {len(published)} article pages')
    
    # Generate index
    index_html = generate_index_page(published, nav_html, footer_html)
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    print('Generated blog/index.html')
    
    # Verify
    files = os.listdir(OUTPUT_DIR)
    html_files = [f for f in files if f.endswith('.html')]
    print(f'Total HTML files in blog/: {len(html_files)}')
    
    # Check a few file sizes
    for fname in sorted(html_files)[:5]:
        size = os.path.getsize(os.path.join(OUTPUT_DIR, fname))
        print(f'  {fname}: {size:,} bytes')

if __name__ == '__main__':
    main()
