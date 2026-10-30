#!/usr/bin/env python3
"""Offline browser comparison against the unmodified, cached original.
Requires playwright, pillow, beautifulsoup4. Run mirror.py once for the reference cache.
All original-site requests are fulfilled from disk, never sent to the live server.
"""
import asyncio, json, hashlib, re, argparse
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from playwright.async_api import async_playwright
from PIL import Image, ImageChops
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.snapshot'
import os
CHROMIUM=os.environ.get('FAW_CHROMIUM')
if not CHROMIUM:
 candidates=sorted((Path.home()/'.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'))
 CHROMIUM=str(candidates[-1]) if candidates else None
def cached_resources():
 result={}
 for path in CACHE.glob('*.json'):
  info=json.loads(path.read_text())
  if isinstance(info,dict) and 'url' in info and path.with_suffix('').exists():
   result[info['url']]=(path.with_suffix('').read_bytes(),info['type'])
 return result
async def reference_route(route,cache,misses):
 u=route.request.url
 if u.startswith('blob:'): return await route.continue_()
 data=cache.get(u)
 if data is None:
  p=urlsplit(u)
  # Only versioned assets may share a cache entry across query strings.
  # Missing search/page/API responses must fail instead of using another document.
  if re.search(r'\.[a-z0-9]+$',p.path,re.I) and '/wp-json/' not in p.path:
   data=next((v for k,v in cache.items() if urlsplit(k).path==p.path and urlsplit(k).netloc==p.netloc),None)
 if data is None:
  misses.append(u); return await route.abort()
 await route.fulfill(body=data[0],content_type=data[1])
async def main():
 args=argparse.ArgumentParser(); args.add_argument('--output',default='/tmp/faw-comparison'); args.add_argument('--quick',action='store_true'); opts=args.parse_args()
 out=Path(opts.output);out.mkdir(exist_ok=True,parents=True)
 cache=cached_resources();manifest=json.loads((CACHE/'manifest.json').read_text())['pages']
 report=[];misses=[];errors=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=CHROMIUM,headless=True,args=['--no-sandbox'])
  reference=await browser.new_context(); await reference.route('**/*',lambda route:reference_route(route,cache,misses))
  local=await browser.new_context()
  external=[]
  async def local_route(route):
   if urlsplit(route.request.url).scheme in ('http','https'):
    external.append(route.request.url);return await route.abort()
   await route.continue_()
  await local.route('**/*',local_route)
  ref=await reference.new_page();copy=await local.new_page()
  copy.on('pageerror',lambda e:errors.append(str(e)))
  copy.on('console',lambda m:errors.append('console: '+m.text) if m.type=='error' else None)
  copy.on('requestfailed',lambda r:errors.append('request: '+r.url+' '+str(r.failure)) if r.failure!='net::ERR_ABORTED' else None)
  for width in ([1440] if opts.quick else [1440,390]):
   await ref.set_viewport_size({'width':width,'height':1000});await copy.set_viewport_size({'width':width,'height':1000})
   cases=list(manifest.items())+[("https://www.faw.at/"+query,"index.html"+query) for query in ['?s=Alfresco','?s=fawzzzznonexistent','?s=','?s=&paged=2']]
   for i,(url,path) in enumerate(cases):
    file_path,sep,query=path.partition('?')
    await asyncio.gather(ref.goto(url,wait_until='networkidle'),copy.goto((ROOT/file_path).as_uri()+(sep+query if sep else ''),wait_until='networkidle'))
    if sep: await copy.wait_for_selector('body.search')
    await asyncio.gather(ref.evaluate('document.fonts.ready'),copy.evaluate('document.fonts.ready'))
    # Compare the slider separately because its timeline depends on render speed.
    if path=='index.html':
     await ref.add_style_tag(content='sr7-module, sr7-module * {visibility:hidden!important}')
     await copy.add_style_tag(content='sr7-module, sr7-module * {visibility:hidden!important}')
    await asyncio.sleep(.5)
    name=f'{width}-{i:02d}';r=out/(name+'-original.png');c=out/(name+'-static.png')
    await ref.screenshot(path=str(r),full_page=True);await copy.screenshot(path=str(c),full_page=True)
    a=Image.open(r).convert('RGB');b=Image.open(c).convert('RGB')
    if a.size==b.size:
     diff=ImageChops.difference(a,b);bbox=diff.getbbox();pixels=sum(1 for pixel in diff.getdata() if max(pixel)>8)
     if bbox:diff.save(out/(name+'-diff.png'))
     result={'width':width,'page':path,'size':a.size,'differentPixels':pixels,'box':bbox}
    else:result={'width':width,'page':path,'originalSize':a.size,'staticSize':b.size}
    report.append(result); print(json.dumps(result),flush=True)
  await copy.goto((ROOT/'index.html').as_uri(),wait_until='networkidle');await copy.wait_for_timeout(1000)
  slider=await copy.evaluate("({keys:Object.keys(SR7.revapi),current:SR7.M.SR7_1_1.current,slides:Object.keys(SR7.M.SR7_1_1.slides)})")
  slider['fonts']=await copy.evaluate("[...document.fonts].filter(f=>f.family.replace(/[\"']/g,'')==='Raleway').map(f=>({weight:f.weight,status:f.status}))")
  if {f['weight'] for f in slider['fonts']}!={'300','400','500','900'}: errors.append('Slider Raleway font definitions missing')
  print('SLIDER',json.dumps(slider),flush=True)
  report={'pages':report,'referenceCacheMisses':misses,'externalRequests':external,'pageErrors':errors,'slider':slider}
  (out/'report.json').write_text(json.dumps(report,indent=2));await browser.close()
  problems=[r for r in report['pages'] if r.get('differentPixels',1)]
  if problems or misses or external or errors: raise SystemExit('FAIL: see '+str(out/'report.json'))
  print('PASS: all '+str(len(report['pages']))+' comparisons match; no missing resources, remote requests, or script errors.')
if __name__=='__main__':asyncio.run(main())
