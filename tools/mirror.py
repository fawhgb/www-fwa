#!/usr/bin/env python3
"""Rate-limited, cached static export of public FAW pages. Never executes PHP."""
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
import hashlib, json, re, time, posixpath, subprocess
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.snapshot'; CACHE.mkdir(exist_ok=True)
BASE='https://www.faw.at/'
USER_AGENT='FAW-Static-Archive/1.0 (single sequential connection; 1 second minimum interval)'
last_request=0
manifest={}
failures={}
def canonical(url):
 p=urlsplit(urljoin(BASE,url)); host=p.netloc.lower()
 return urlunsplit(('https', 'www.faw.at' if host in ('faw.at','www.faw.at') else host,p.path or '/',p.query,''))
def internal(url): return urlsplit(url).netloc in ('www.faw.at','faw.at')
def path_for(url, page=False):
 p=urlsplit(url); path=unquote(p.path).lstrip('/')
 if page: return Path(path)/'index.html'
 if not internal(url): path='assets/external/'+p.netloc+'/'+path
 if p.netloc=='fonts.googleapis.com': path='assets/external/fonts-google-'+hashlib.sha256(url.encode()).hexdigest()[:12]+'.css'
 if not path or path.endswith('/'): path+='index.html'
 return Path(path)
def fetch(url):
 global last_request
 url=canonical(url); key=hashlib.sha256(url.encode()).hexdigest(); dst=CACHE/key
 info=CACHE/(key+'.json')
 if dst.exists() and info.exists(): return dst.read_bytes(),json.loads(info.read_text())['type']
 time.sleep(max(0,1.05-(time.monotonic()-last_request)))
 last_request=time.monotonic()
 try:
  result=subprocess.run(['curl','--fail','--location','--compressed','--silent','--show-error','--max-time','40','--user-agent',USER_AGENT,'--output',str(dst),'--write-out','%{content_type}',url],capture_output=True)
  if result.returncode: raise RuntimeError(result.stderr.decode())
  data=dst.read_bytes(); typ=result.stdout.decode()
  if len(data)>30_000_000: raise ValueError('Unexpected large resource')
  info.write_text(json.dumps({'url':url,'type':typ}))
  print('GET',200,len(data),url,flush=True)
  return data,typ
 except Exception as e:
  if re.search(r'\b(?:429|502|503|504)\b',str(e)): raise SystemExit('Server busy; archive stopped: '+str(e))
  failures[url]=str(e); print('FAILED',url,str(e),flush=True); return None,''
def is_page(url):
 p=urlsplit(url)
 return internal(url) and not p.query and not re.search(r'\.[^/]+$',p.path) and not p.path.startswith(('/wp-','/feed/','/author/','/tag/','/category/'))
pages={}; queue=[BASE]
while queue:
 url=queue.pop(0)
 if url in pages: continue
 data,typ=fetch(url)
 if data is None: continue
 if 'html' not in typ: continue
 soup=BeautifulSoup(data,'html5lib'); pages[url]=soup; manifest[url]=str(path_for(url,True))
 for a in soup.select('a[href]'):
  u=canonical(urljoin(url,a['href']))
  if is_page(u) and u not in pages and u not in queue: queue.append(u)
 if len(pages)>100: raise RuntimeError('Page limit exceeded')
(CACHE/'pages.json').write_text(json.dumps(list(pages),indent=2))
print('PAGES',len(pages),flush=True)
search_sources={}
for query in ('?s=', '?s=&paged=2', '?s=fawzzzznonexistent', '?s=Alfresco'):
 data,_=fetch(BASE+query)
 search_sources[BASE+query]=BeautifulSoup(data,'html5lib')
resources={}
css_url=re.compile(r'url\(\s*([\'"]?)(.*?)\1\s*\)', re.I)
abs_url=re.compile(r'(?:https?:)?//(?:www\.)?faw\.at/[^\s<>"\'\\)]+')
def add_resource(url):
 url=canonical(url)
 if url in manifest: return manifest[url]
 if url in resources: return resources[url]
 if urlsplit(url).scheme not in ('http','https'): return None
 if not internal(url) and urlsplit(url).netloc not in ('fonts.googleapis.com','fonts.gstatic.com','images.wko.at'): return None
 if re.search(r'\.(?:php|html?)$',urlsplit(url).path) or '/wp-json/' in url: return None
 if not re.search(r'\.[^/]+$',urlsplit(url).path) and urlsplit(url).netloc!='fonts.googleapis.com': return None
 path=path_for(url); resources[url]=str(path)
 return str(path)
def discover_text(text,base):
 for m in css_url.finditer(text):
  if m[2] and not m[2].startswith(('data:','#')) and not any(c in m[2] for c in ['$', '{', '}', '+']) and re.search(r'\.(?:png|jpe?g|gif|webp|svg|css|woff2?|ttf|eot|ico)(?:[?#]|$)', m[2], re.I): add_resource(urljoin(base,m[2]))
 for m in abs_url.finditer(text):
  u=canonical(m[0])
  if re.search(r'\.(?:png|jpe?g|gif|webp|svg|css|js|woff2?|ttf|eot|pdf|ico)(?:\?|$)',u,re.I): add_resource(u)
for url,soup in list(pages.items())+list(search_sources.items()):
 for tag in soup.find_all(True):
  for attr in ('src','data-src','data-lazy-src','poster','data-thumb','data-lazyload'):
   if tag.get(attr) and not tag[attr].startswith(('data:','blob:')): add_resource(urljoin(url,tag[attr]))
  if tag.get('href') and (tag.name=='a' and not is_page(canonical(urljoin(url,tag['href']))) or tag.name=='link' and set(tag.get('rel',[])) & {'stylesheet','icon','apple-touch-icon'}):
   if tag['href'] and not tag['href'].startswith(('#','mailto:','tel:')): add_resource(urljoin(url,tag['href']))
  for attr in ('srcset','data-srcset','data-lazy-srcset'):
   for item in tag.get(attr,'').split(','):
    if item.strip(): add_resource(urljoin(url,item.strip().split()[0]))
 discover_text(str(soup),url)
# Slider's lazy slide payloads and runtime CSS must be available without its REST API.
slider_payloads={}
for slide in ('4','5','6'):
 data,_=fetch(BASE+'wp-json/sliderrevolution/sliders/1?srengine=7&slideid='+slide)
 if data is None: raise RuntimeError('Missing slider payload '+slide)
 slider_payloads.update(json.loads(data)['slides'])
 discover_text(data.decode(),BASE)
for name in ('preloaders/t0.css','sr7.lp.css','sr7.media.css'):
 add_resource(BASE+'wp-content/plugins/revslider/public/css/'+name)
processed={}
while True:
 pending=[u for u in resources if u not in processed]
 if not pending: break
 for url in pending:
  data,typ=fetch(url); processed[url]=(data,typ)
  if data is not None and ('.css' in urlsplit(url).path or 'text/css' in typ): discover_text(data.decode('utf-8','replace'),url)
  if data is not None and ('.js' in urlsplit(url).path):
   txt=data.decode('utf-8','replace'); discover_text(txt,url)
   # SR7 runtime assets are resolved at runtime from plugin_url.
   for suffix in re.findall(r'["\']([^"\']*public/[^"\']+\.(?:js|css))["\']',txt):
    if not any(x in suffix for x in ['+','${']): add_resource(urljoin(BASE+'wp-content/plugins/revslider/',suffix))
# All references are relative, including explicit index.html links for file:// browsing.
def relative(target,source): return posixpath.relpath(target,posixpath.dirname(source) or '.')
def rewrite_url(raw,base,source):
 if not raw or raw.startswith(('#','data:','mailto:','tel:','javascript:','blob:')): return raw
 p=urlsplit(urljoin(base,raw)); u=canonical(urljoin(base,raw))
 dest=manifest.get(u) or resources.get(u)
 if dest and (u in manifest or processed.get(u,(None,''))[0] is not None): return relative(dest,source)+('#'+p.fragment if p.fragment else '')
 return raw
for url,(data,typ) in processed.items():
 if data is None: continue
 path=resources[url]; dst=ROOT/path; dst.parent.mkdir(parents=True,exist_ok=True)
 if '.css' in urlsplit(url).path or 'text/css' in typ:
  txt=data.decode('utf-8','replace'); txt=css_url.sub(lambda m:'url('+m[1]+rewrite_url(m[2],url,path)+m[1]+')',txt); data=txt.encode()
 if '.js' in urlsplit(url).path:
  txt=data.decode('utf-8','replace')
  txt=txt.replace('fn: function() { if (window._tpt', 'fn: function() { if (!document.getElementById("SR7_1_1")) return; if (window._tpt')
  # file:// images cannot be requested with anonymous CORS; HTTP keeps original behavior.
  txt=txt.replace('n&&(i.crossOrigin="anonymous")', 'n&&new URL(e,document.baseURI).protocol!=="file:"&&(i.crossOrigin="anonymous")')
  marker="SR7.JSON['SR7_1_1'] = "
  if marker in txt:
   start=txt.index(marker)+len(marker); obj,end=json.JSONDecoder().raw_decode(txt[start:])
   obj['slides'].update(slider_payloads)
   txt=txt[:start]+json.dumps(obj,ensure_ascii=False)+txt[start+end:]
  # Absolute URLs become runtime-local URLs, also when opened via file://.
  local_map={}
  for u,dest in {**manifest,**resources}.items():
   if u in resources and processed.get(u,(None,''))[0] is None: continue
   local_map[u]=dest; local_map[u.replace('https:','')]=dest
  # Replace only quoted literals, never pieces of JavaScript code.
  def js_local(m):
   raw=m[2]; clean=raw.replace('\\/','/')
   if clean in local_map: return 'window.FAW_STATIC_ROOT+'+json.dumps(local_map[clean])
   # Script paths to the plugin are also generated by the slider.
   for prefix in ('https://www.faw.at/','//www.faw.at/'):
    if clean.startswith(prefix) and clean.endswith('/'):
     return 'window.FAW_STATIC_ROOT+'+json.dumps(clean[len(prefix):])
   return m[0]
  txt=re.sub(r"([\"'])([^\"'\n]*)(?:\1)",js_local,txt)
  data=txt.encode()
 dst.write_bytes(data)
for url,soup in pages.items():
 path=manifest[url]
 for tag in list(soup.select('link[rel], meta[name="generator"], script[type="speculationrules"], script#contact-form-ajax-js-extra')):
  if tag.name!='link' or set(tag.get('rel',[])) & {'pingback','alternate','EditURI','shortlink','preconnect','https://api.w.org/','profile'}: tag.decompose()
 for tag in soup.find_all(True):
  for attr in ('src','href','data-src','data-lazy-src','poster','data-thumb','data-lazyload','content','action'):
   if tag.get(attr): tag[attr]=rewrite_url(tag[attr],url,path)
  for attr in ('srcset','data-srcset','data-lazy-srcset'):
   if tag.get(attr): tag[attr]=', '.join(' '.join([rewrite_url(x.strip().split()[0],url,path)]+x.strip().split()[1:]) for x in tag[attr].split(',') if x.strip())
  if tag.get('style'): tag['style']=css_url.sub(lambda m:'url('+m[1]+rewrite_url(m[2],url,path)+m[1]+')',tag['style'])
 for tag in soup.select('style'):
  tag.string=css_url.sub(lambda m:'url('+m[1]+rewrite_url(m[2],url,path)+m[1]+')',str(tag.string or ''))
 # Keep script bytes/JSON unchanged except URLs pointing at downloaded files.
 for tag in soup.select('script:not([src])'):
  if tag.string:
   txt=tag.string
   def local_inline(m):
    clean=m[2].replace('\\/','/')
    if clean in manifest: return json.dumps(relative(manifest[clean],path))
    if clean in resources and processed.get(clean,(None,''))[0] is not None: return json.dumps(relative(resources[clean],path))
    for prefix in ('https://www.faw.at/','//www.faw.at/'):
     if clean.startswith(prefix) and clean.endswith('/'):
      return 'window.FAW_STATIC_ROOT+'+json.dumps(clean[len(prefix):])
    return m[0]
   txt=re.sub(r"([\"'])([^\"'\n]*)(?:\1)",local_inline,txt)
   txt=re.sub(r"SR7\.E\.(?:ajaxurl|resturl)\s*=.*?;",'',txt)
   tag.string=txt
 root_script=soup.new_tag('script')
 root_script.string='window.FAW_STATIC_ROOT=new URL('+json.dumps(relative('index.html',path))+',location.href).href.replace(/index\\.html$/, "");'
 soup.head.insert(0,root_script)
 runtime=soup.new_tag('script',src=relative('assets/static.js',path)); runtime['defer']=''; soup.head.append(runtime)
 dst=ROOT/path; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(str(soup))
(ROOT/'.nojekyll').touch()
(CACHE/'manifest.json').write_text(json.dumps({'pages':manifest,'resources':resources,'failures':failures},indent=2))
print('DONE',len(pages),'pages',len(processed),'resources',len(failures),'failures',flush=True)

# Search uses the original result templates and excerpts, without a search backend.
search_pages=[]
for query in ('?s=','?s=&paged=2'):
 data,_=fetch(BASE+query)
 search_pages.append(BeautifulSoup(data,'html5lib'))
index=[]
for results in search_pages:
 for article in results.select('article'):
  link=article.select_one('.entry-title a'); url=canonical(link['href'])
  source=pages[url].select_one('.entry-content')
  index.append({'title':link.get_text(' ',strip=True),'path':manifest[url], 'text':source.get_text(' ',strip=True), 'html':str(article)})
search_template=search_pages[0].select_one('#main')
for tag in list(search_template.select('article,#nav-below')): tag.decompose()
empty,_=fetch(BASE+'?s=fawzzzznonexistent')
search_data={'pages':index,'template':str(search_template),'empty':str(BeautifulSoup(empty,'html5lib').select_one('#main'))}
assets=ROOT/'assets'; assets.mkdir(exist_ok=True)
(assets/'search-index.js').write_text('window.FAW_SEARCH_DATA = '+json.dumps(search_data,ensure_ascii=False)+';\n')
