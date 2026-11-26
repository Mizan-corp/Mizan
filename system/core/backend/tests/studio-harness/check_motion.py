"""Reduced local motion contract tests. Platform/SDK schemas and Python render, no full-app claim."""
import copy,importlib.util,json,os,sys
from pathlib import Path
sys.path.insert(0,os.environ.get('STUDIO_BACKEND_ROOT','/tmp/pgtest'))
from app.framework.manifest import page_problems
from app.platform.site.render import render_page,render_document
root=Path(os.environ.get('STUDIO_WORK_ROOT','/home/sandbox/parity-wip'))
platform=(root/'backend/app/framework/manifest.py').read_bytes();sdk=(root/'sdk/python/mizan_sdk/manifest.py').read_bytes();assert platform==sdk
spec=importlib.util.spec_from_file_location('sdk_motion',root/'sdk/python/mizan_sdk/manifest.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
tree=json.load(open('/downloads/native-category-trees.json'))[0]['tree'];target=tree['children'][0]
for effect in ['none','fade','rise','slide','zoom']:
 candidate=copy.deepcopy(tree);candidate['children'][0]['settings']['desktop'].update(animation=effect,animation_speed='slow',animation_delay='short');assert not page_problems(candidate);assert not module.page_problems(candidate);assert 'mz-animation-'+effect in render_page(candidate,lang='en');candidate['children'][0]['settings']['mobile']['animation']='none';assert 'mz-animation-'+effect not in render_page(candidate,lang='en',device='mobile') if effect!='none' else True
bad=copy.deepcopy(tree);bad['children'][0]['settings']['desktop']['animation']='url(evil)';assert page_problems(bad);assert module.page_problems(bad)
target['settings']['desktop'].update(animation='rise',animation_speed='slow',animation_delay='short');doc=render_document(tree,meta={'title':'Motion export test'},lang='en');assert 'prefers-reduced-motion:reduce' in doc and 'animation:none!important' in doc;Path('/downloads/native-motion-export.html').write_text(doc)
print('PASS platform/SDK exact schemas, five effects acceptance, invalid refusal, Python classes/device override/reduced-motion CSS and exported document')
