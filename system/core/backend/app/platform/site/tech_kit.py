"""First-party technical-business composition. Sample copy, no data or action binding."""
TECH_KIT='tech-business-v0'
PAGES=(('home','Home'),('products','Products'),('services','Services'),('contact','Contact'))
def theme(prefix):
 links=[{'label':title,'href':'/'+prefix+'-'+key} for key,title in PAGES]
 return {'colors':{'light':{'background':'#F0F5F8','foreground':'#092331','card':'#FFFFFF','primary':'#007DA6','primary-foreground':'#FFFFFF'}},'typography':{'family':'sans-serif'},'shape':{'radius':18},'header':{'brand':'CIRCUIT / sample','links':links,'actions':[]},'footer':{'lines':['CIRCUIT / Technical business starter','Sample content. No services, orders or messages are connected.'],'links':links}}
def make_tech_pages(prefix):
 result=[]
 for index,(key,title) in enumerate(PAGES):
  counter=0
  def n(kind,content=None,kids=None,settings=None):
   nonlocal counter
   counter+=1
   return {'id':f'n_tech{index}{counter:04d}','type':kind,'settings':settings or {},'content':{'en':content} if content else {},**({'children':kids} if kids is not None else {})}
  def h(text,level=2):return n('heading',{'text':text},settings={'desktop':{'level':level}})
  def t(text,variant='body'):return n('text',{'html':'<p>'+text+'</p>'},settings={'desktop':{'variant':variant}})
  def b(label,dest):return n('button',{'label':label,'href':'/'+prefix+'-'+dest},settings={'desktop':{'style':'primary'}})
  def col(kids,card=False):return n('column',kids=kids,settings={'desktop':{'padding':'m' if card else 's',**({'background':'card','rounded':True} if card else {})},'mobile':{'padding':'s'}})  # mobile padding stays inset so a background added later never clips text at band edges
  def row(cols,card=False):return n('columns',kids=[col(c,card) for c in cols],settings={'desktop':{'columns':len(cols),'gap':'m'},'mobile':{'stack':True,'gap':'s'}})
  def gap():return row([[t(' ', 'note')]])
  def art(name):return n('image',{'src':'/studio-assets/tech-'+name+'.svg','alt':'Illustrative '+name+', not an actual product'},settings={'desktop':{'rounded':True}})
  if key=='home':
   children=[row([[t('TECH / SERVICE / EVERYDAY','eyebrow'),h('Good technology. A clearer next step.',1),t('A considered home for your devices, repairs and technical services.'),b('Explore the catalog','products')],[art('workbench')]]),row([[h('Find your next device'),t('Laptops, storage and essentials. Build a catalog around the products you choose to share.'),b('View products','products')],[h('Keep what matters working'),t('Give repair, upgrades and support their own space, with a clear path to your team.'),b('Explore services','services')]],True),row([[t('ONE BUSINESS. CONNECTED PAGES.','eyebrow'),h('From a useful part to a fresh start.'),t('Use this editable composition to introduce your own business. Replace sample copy before sharing.'),b('Start a conversation','contact')]])]
  elif key=='products':
   children=[row([[t('THE CATALOG','eyebrow'),h('The right tools for what comes next.',1),t('Introduce the categories you sell. These illustrated cards are editable examples, not connected stock.')]]),row([[art('laptop'),h('Laptops & computers',3),t('A place for portable workstations and everyday devices.')],[art('storage'),h('Storage & memory',3),t('A place for drives, memory and useful upgrades.')],[art('accessories'),h('Everyday essentials',3),t('A place for accessories that make the setup complete.')]],True),row([[t('YOUR PRODUCTS, LIVE','eyebrow'),h('Selected from your catalog.'),t('Connect this section to products you choose in Studio under Module data. Until you connect it, the sample card below is placeholder copy, not a real product. If no products are consented, the connected section hides itself.')]]),row([[art('laptop'),h('Selected product name',3),t('Optional display price')]],True),row([[h('Looking for something specific?'),t('Add your verified contact details and delivery workflow before taking enquiries.'),b('Contact page','contact')]])]
  elif key=='services':
   children=[row([[t('SERVICE & SUPPORT','eyebrow'),h('Give good devices a longer life.',1),t('Make your services easy to understand, from the first question to the next step.'),b('Contact page','contact')],[art('workbench')]]),row([[h('01 / Repair',3),t('Explain the faults you diagnose and the work your team can take on.')],[h('02 / Upgrades',3),t('Explain compatibility checks, fitting and the changes customers can expect.')],[h('03 / Support',3),t('Explain the technical help you offer to homes and businesses.')]],True),row([[h('A process people can follow.'),t('Describe how you receive a request, assess the work, agree the scope and hand it back. Sample process only; no repair workflow is connected.')]])]
  else:
   children=[row([[t('LET’S TALK TECH','eyebrow'),h('What can we help you move forward?',1),t('Use this page to tell visitors how to reach your business. Add only contact details you have verified.')],[art('accessories')]]),row([[h('Visit the workshop',3),t('Your verified location and opening hours belong here. No address has been added.')],[h('Speak to the team',3),t('Send a message through this form; the team reads every message in the Website tab.'),
    n('form',{'title':'Contact us','name_label':'Name','email_label':'Email','message_label':'Message','submit_label':'Send','success_message':'Thank you! We will get back to you soon.'},settings={'desktop':{'field_name':True,'field_phone':False}})]],True),row([[h('Keep exploring'),t('Find your way back to the products and services pages.'),b('Browse products','products'),b('Explore services','services')]])]
  tree=n('section',kids=children,settings={'desktop':{'background':'background','padding':'none','max_width':'wide'},'mobile':{'padding':'none'}})
  result.append({'slug':prefix+'-'+key,'titles':{'en':title},'tree':tree})
 return result
