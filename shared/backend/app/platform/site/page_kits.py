"""First-party multi-page draft starter, never imports or activates a storefront."""
from copy import deepcopy
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import SitePage
from . import service
from .tech_kit import TECH_KIT, make_tech_pages

KIT_ID='catalog-pages-v0'
SCHEMA='mizan.draft-page-kit.experimental.v0'
PAGES=(('home','Home'),('products','Products'),('about','About'),('contact','Contact'))

def kit_catalog():
    return {'schema':SCHEMA,'items':[{'id':KIT_ID,'name':'Catalog page set','description':'Four editable draft pages. No shared design, product connection, public navigation, Help Desk, forms or checkout.','pages':[{'key':key,'title':title} for key,title in PAGES]},{'id':TECH_KIT,'name':'Technical business','description':'Four designed native sample pages. Shared design is a separate explicit save; no business actions or publication.','pages':[{'key':key,'title':title} for key,title in (('home','Home'),('products','Products'),('services','Services'),('contact','Contact'))]}]}

def make_pages(prefix,kit_id=KIT_ID):
    # Prefix is compulsory, so a starter never targets existing home/products pages.
    prefix=service.check_slug(prefix)
    if len(prefix)>40:raise HTTPException(422,'Use a draft address prefix up to 40 characters.')
    if kit_id==TECH_KIT:return make_tech_pages(prefix)
    if kit_id!=KIT_ID:raise HTTPException(422,'Unknown reviewed draft page kit.')
    result=[]
    for index,(key,title) in enumerate(PAGES):
        counter=0
        def node(kind,content=None,children=None,settings=None):
            nonlocal counter
            counter+=1
            return {'id':f'n_kit{index}{counter:04d}','type':kind,'settings':settings or {},'content':{'en':content} if content else {},**({'children':children} if children is not None else {})}
        def text(value):return node('text',{'html':'<p>'+value+'</p>'})
        def heading(value,level=2):return node('heading',{'text':value},settings={'desktop':{'level':level}})
        def row(children):return node('columns',children=[node('column',children=children)],settings={'desktop':{'columns':1,'gap':'m'},'mobile':{'stack':True}})
        intro={'home':'A starting point for your website. Edit the words and arrange the sections.','products':'Connect explicitly selected inventory products in Studio. No records are connected by this starter.','about':'Write your own story here. Do not present starter copy as real business facts.','contact':'Add verified contact details before use. No form or message is connected.'}[key]
        children=[row([heading(title,1),text(intro)])]
        if key=='home':children.append(row([heading('Explore the page set'),text('Home, products, about and contact are separate editable drafts. Public navigation is not installed.')]))
        if key=='products':children.append(row([heading('Your catalog'),text('Add product-card blocks and choose website consent and section products separately. Prices and images are off by default.')]))
        if key=='about':children.append(row([heading('What matters to you'),text('Replace this instruction with information you have chosen to share.')]))
        if key=='contact':children.append(row([heading('Before visitors can contact you'),text('Choose a real destination and supported delivery workflow. This draft sends nothing.')]))
        result.append({'slug':prefix+'-'+key,'titles':{'en':title},'tree':node('section',children=children)})
    return result

async def install_kit(db,kit_id,prefix):
    if kit_id not in (KIT_ID,TECH_KIT):raise HTTPException(422,'Unknown reviewed draft page kit.')
    pages=make_pages(prefix,kit_id)
    # Validate the entire fixed package before any insert. No supplied trees or plugin code.
    for page in pages:await service.check_bound_tree(db,page['tree'])
    slugs=[p['slug'] for p in pages]
    existing=(await db.execute(select(SitePage.slug).where(SitePage.slug.in_(slugs)))).scalars().all()
    if existing:raise HTTPException(409,'One or more page addresses already exist. Nothing was installed.')
    rows=[SitePage(slug=p['slug'],titles=deepcopy(p['titles']),draft_tree=deepcopy(p['tree']),status='draft') for p in pages]
    db.add_all(rows)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409,'A page address changed while installing. Nothing was installed.') from None
    for row in rows:
        await db.refresh(row)
    return rows
