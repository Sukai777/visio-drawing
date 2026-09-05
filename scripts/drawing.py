"""Compile, audit and compare editable diagrams. No model/provider API calls."""
import argparse
import collections
import hashlib
import json
import math
import re
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'v': 'http://schemas.microsoft.com/office/visio/2012/main'}
CIRCUIT = {'resistor','capacitor','inductor','nmos','pmos','nmos4','pmos4','npn','pnp',
           'ground','line_section','pad','current_source','voltage_source'}
GENERIC = {'process','decision','terminator','data','ellipse','container'}
CUSTOM = GENERIC | {'current_source','voltage_source'}

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def write(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def require(ok, message):
    if not ok: raise ValueError(message)

def catalog():
    cat = read(ROOT/'assets/components.json')['components']
    for typ in sorted(CUSTOM):
        points = {'A':(.5,1),'B':(.5,0)} if typ.endswith('_source') else {'L':(0,.5),'R':(1,.5),'T':(.5,1),'B':(.5,0)}
        if typ=='data': points={'L':(.1,.5),'R':(.9,.5),'T':(.6,1),'B':(.4,0)}
        cat[typ] = {'master':typ, 'width':1,'height':1,
                    'pins':{p:{'row':i,'u':uv[0],'v':uv[1]} for i,(p,uv) in enumerate(points.items())}}
    return cat

class Union:
    def __init__(self): self.p={}
    def root(self,x):
        self.p.setdefault(x,x)
        if self.p[x]!=x: self.p[x]=self.root(self.p[x])
        return self.p[x]
    def join(self,a,b): self.p[self.root(a)]=self.root(b)

def netcheck(components, wires, evidence, cat):
    uf=Union(); valid=set(); required=set()
    for c in components:
        pins={c['id']+'.'+p for p in cat[c['type']]['pins']}
        valid |= pins
        if c['type'] in CIRCUIT and c['type'] not in {'ground','pad'}: required |= pins
        if c['type']=='pad':
            for p in pins: uf.join(c['id']+'.A',p)
        if c['type']=='ground': uf.join('@GND:'+c.get('ground_domain','0'),c['id']+'.P')
    for w in wires:
        require(w['from'] in valid and w['to'] in valid, 'Unknown endpoint in '+str(w))
        if w.get('kind','wire')=='wire': uf.join(w['from'],w['to'])
    assigned={}; roots={}
    for name,ends in evidence.get('nets',{}).items():
        require(bool(ends), 'Empty net '+name)
        require(set(ends)<=valid, 'Unknown expected endpoint in '+name)
        group={uf.root(e) for e in ends}
        require(len(group)==1, 'Open expected net '+name+': '+str(ends))
        root=next(iter(group))
        require(root not in roots, 'Short between '+name+' and '+roots.get(root,''))
        roots[root]=name
        for e in ends:
            require(e not in assigned, 'Duplicate net assignment '+e); assigned[e]=name
    require(required<=set(assigned), 'Missing expected pin assignments: '+str(sorted(required-set(assigned))))
    open_pins=evidence.get('open_pins',{})
    for name,ends in evidence.get('nets',{}).items():
        if len(ends)==1 and ends[0] in required:
            require(bool(open_pins.get(ends[0])), 'Singleton pin needs source evidence: '+ends[0])
    for endpoint,reason in open_pins.items():
        require(endpoint in valid and bool(reason), 'Invalid open pin evidence '+endpoint)
        peers={p for p in valid if uf.root(p)==uf.root(endpoint)}
        # Invisible drawing junctions can extend a legitimately open terminal.
        peer_devices={p for p in peers if next(c for c in components if c['id']==p.split('.')[0])['type']!='junction'}
        require(peer_devices=={endpoint}, 'Expected open pin is connected: '+endpoint)
    for a,b in evidence.get('must_connect',[]):
        require(a in valid and b in valid and uf.root(a)==uf.root(b), 'Required connection missing: '+a+' / '+b)
    for a,b in evidence.get('must_separate',[]):
        require(a in valid and b in valid and uf.root(a)!=uf.root(b), 'Forbidden connection: '+a+' / '+b)
    expected=collections.Counter((e['from'],e['to'],e.get('label',''),e.get('arrow','end')) for e in evidence.get('edges',[]))
    actual=collections.Counter((e['from'],e['to'],e.get('label',''),e.get('arrow','end')) for e in wires if e.get('kind')=='edge')
    require(expected==actual, 'Directed edge/branch-label mismatch: '+str(expected-actual)+' extra '+str(actual-expected))

def record(evidence_path, lock_path):
    evidence_path=Path(evidence_path).resolve(); lock_path=Path(lock_path)
    ev=read(evidence_path)
    require(ev.get('inventory') and ev.get('panels'), 'Evidence needs inventory and panels')
    source=(evidence_path.parent/ev['source']).resolve()
    require(source.is_file(), 'Reference image missing: '+str(source))
    require(not lock_path.exists(), 'Evidence lock already exists; retain it. For a justified correction use a new lock filename and evidence.revision_reason.')
    require(ev.get('reviewed_from_source') is True, 'Inspect source before recording evidence')
    write(lock_path, {'evidence':str(evidence_path),'evidence_sha256':digest(evidence_path),
                     'source':str(source),'source_sha256':digest(source),'snapshot':ev})
    return {'status':'recorded','lock':str(lock_path)}

def loadlock(p):
    lock=read(p)
    require(digest(lock['evidence'])==lock['evidence_sha256'], 'Evidence changed after recording; re-read source and retain an explicit revision')
    require(digest(lock['source'])==lock['source_sha256'], 'Source image changed after recording')
    return lock

def label_text(label):
    return ''.join(r['text'] for r in label['runs']) if 'runs' in label else label.get('text','')

def prepare(model_path, lock_path, out):
    m=read(model_path); lock=loadlock(lock_path); ev=lock['snapshot']; cat=catalog()
    require(m.get('version')==2, 'Use model version 2')
    require('arrows' not in m and 'backgrounds' not in m, 'Use typed annotations, not legacy arrows/backgrounds fields')
    require(len(m['canvas'])==2 and min(m['canvas'])>0, 'Invalid canvas')
    panels={p['id']:p for p in m['panels']}; epanels={p['id']:p for p in ev['panels']}
    require(len(panels)==len(m['panels']) and set(panels)==set(epanels), 'Panel IDs do not match evidence')
    inv={c['id']:c for c in ev['inventory']}
    require(len(inv)==len(ev['inventory']), 'Duplicate source inventory IDs')
    comps=m.get('components',[]); ids=[c['id'] for c in comps]
    require(len(set(ids))==len(ids) and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',s) for s in ids), 'Invalid/duplicate component ID')
    require(set(ids)==set(inv), 'Inventory mismatch. Missing '+str(set(inv)-set(ids))+'; extra '+str(set(ids)-set(inv)))
    warnings=[]; compiled=[]; profiles=m.get('styles',{}); placements={}
    body_metrics=read(ROOT/'assets/body-metrics.json')
    for item in comps:
        c=dict(item); typ=c['type']; ident=c['id']; evidence=inv[ident]
        require(typ in cat and typ!='junction', 'Unsupported device '+typ+'; implement a typed, pinned primitive before use')
        require(evidence['type']==typ and evidence['panel']==c['panel'], 'Type/panel mismatch '+ident)
        require(evidence.get('bbox') and len(evidence['bbox'])==4, 'Missing source bounds '+ident)
        require(evidence.get('role','')==c.get('role',''), 'Semantic role mismatch '+ident)
        require(evidence.get('parent')==c.get('parent'), 'Container ownership mismatch '+ident)
        for meaning_color in ('color','fill'):
            if meaning_color in evidence: require(evidence[meaning_color].lower()==c.get(meaning_color,'').lower(),'Source color role mismatch '+ident)
        if typ in CIRCUIT:
            require('w' not in c and 'h' not in c, 'Circuit symbols use size/profile, never independent w/h: '+ident)
            profile=profiles.get(c.get('profile',typ),{})
            span=profile.get('span', {'ground':20,'pad':9,'line_section':36,'current_source':40,'voltage_source':40}.get(typ,48))
            size=c.get('size',1)
            require(size>0 and span>0,'Nonpositive symbol size '+ident)
            baseline=profile.get('aspect',cat[typ]['width']/cat[typ]['height'])
            if 'aspect' in profile: require(profile.get('source_reason'),'Custom aspect requires a source calibration reason')
            require(baseline>0,'Aspect must be positive')
            require(not ('body_width' in profile and 'body_height' in profile),'Choose one body dimension; preserve shape aspect')
            if 'body_width' in profile or 'body_height' in profile:
                require(typ in body_metrics and isinstance(body_metrics[typ],dict),'No measured body geometry for '+typ+'; use span and inspect catalog')
                metrics=body_metrics[typ]
                if 'body_width' in profile: span=profile['body_width']/metrics['width_fraction']/baseline
                else: span=profile['body_height']/metrics['height_fraction']
                require(span>0,'Body dimension must be positive')
            if abs(size-1)>.25: require(c.get('size_reason'),'Size override >25% requires source/layout reason: '+ident)
            if typ=='line_section': c['w']=span*size; c['h']=span*size/baseline
            else: c['h']=span*size; c['w']=span*size*baseline
            c['size_group']=c.get('profile',typ)
        else:
            require(c.get('w',0)>0 and c.get('h',0)>0, 'Generic shapes need positive w/h '+ident)
        p=panels[c['panel']]; scale=p.get('scale',1)
        require(scale>0,'Panel scale must be positive')
        require(c.get('anchor') in cat[typ]['pins'] or not c.get('anchor'),'Unknown anchor '+ident)
        c['at']=[p['at'][0]+c['at'][0]*scale,p['at'][1]+c['at'][1]*scale]
        c['w']*=scale; c['h']*=scale
        c['text']=label_text(c)
        require(label_text(evidence)==c['text'], 'Component label mismatch '+ident)
        placements[ident]=c; compiled.append(c)
    for c in compiled:
        if c.get('parent'):
            require(c['parent'] in placements and placements[c['parent']]['type']=='container', 'Unknown container '+c['id'])
    nodeids=set()
    source_junctions={n['id']:n for n in ev.get('junctions',[])}
    visible_junctions={n['id']:n for n in m.get('nodes',[]) if not n.get('hidden',False)}
    require(set(source_junctions)==set(visible_junctions),'Visible junction inventory mismatch')
    for ident,n in visible_junctions.items():
        require(source_junctions[ident]['panel']==n['panel'] and len(source_junctions[ident]['bbox'])==4,'Junction evidence mismatch '+ident)
    for node in m.get('nodes',[]):
        n=dict(node); p=panels[n['panel']]; s=p.get('scale',1)
        require(n['id'] not in placements and n['id'] not in nodeids,'Duplicate node '+n['id'])
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',n['id']) is not None,'Invalid node ID')
        nodeids.add(n['id']); n['at']=[p['at'][i]+n['at'][i]*s for i in range(2)]
        n.update(type='junction',w=n.get('diameter',4)*s,h=n.get('diameter',4)*s)
        compiled.append(n)
    wires=[]; edgeids=set()
    for i, wire in enumerate(m.get('wires',[])):
        w=dict(wire); w.setdefault('id','w'+str(i)); w.setdefault('kind','wire')
        require(w['id'] not in edgeids,'Duplicate wire ID'); edgeids.add(w['id'])
        require(w['kind'] in {'wire','edge'},'Invalid wire kind')
        if w['kind']=='wire': require(w.get('arrow','none')=='none','Electrical wires cannot have arrowheads')
        else: require(w.get('arrow','end') in {'end','both','none'},'Unsupported edge arrow')
        if w.get('via'):
            p=panels[w['panel']]; s=p.get('scale',1)
            require(all(isinstance(v,list) and len(v)==2 for v in w['via']),'via must be nested x/y pairs')
            w['via']=[[p['at'][i]+v[i]*s for i in range(2)] for v in w['via']]
        wires.append(w)
    netcheck(compiled,wires,ev,cat)
    labels=[]
    for item in m.get('labels',[]):
        require('sub_from' not in item, 'Use text runs with sub/sup flags instead of legacy sub_from')
        lab=dict(item); p=panels[lab['panel']]; s=p.get('scale',1)
        lab['at']=[p['at'][i]+lab['at'][i]*s for i in range(2)]
        lab['w']=lab.get('w',80)*s; lab['h']=lab.get('h',24)*s; lab['text']=label_text(lab)
        labels.append(lab)
    source_labels=collections.Counter(ev.get('labels',[]))
    actual_labels=collections.Counter(l['text'] for l in labels if l.get('role','source')=='source')
    require(actual_labels==source_labels, 'Source text inventory mismatch')
    annotations=[]
    for ann in m.get('annotations',[]):
        a=dict(ann); require(a['kind'] in {'frame','arrow','line'},'Unsupported annotation kind')
        require(a.get('purpose'),'Annotations need explanatory purpose; devices must be components')
        p=panels[a['panel']]; s=p.get('scale',1)
        if 'points' in a: a['points']=[[p['at'][i]+v[i]*s for i in range(2)] for v in a['points']]
        if 'at' in a:
            a['at']=[p['at'][i]+a['at'][i]*s for i in range(2)]; a['w']*=s; a['h']*=s
        annotations.append(a)
    unresolved=ev.get('uncertainties',[])
    out=Path(out)
    result={**m,'components':compiled,'nodes':[],'wires':wires,'labels':labels,'annotations':annotations,
            'extra_types':{t:cat[t] for t in sorted(CUSTOM)}, 'source_lock':str(Path(lock_path).resolve()),
            'evidence_sha256':lock['evidence_sha256'],'source_sha256':lock['source_sha256'],
            'preflight':{'topology':'passed','inventory':'passed','uncertainties':unresolved,'warnings':warnings}}
    write(out,result)
    return {'status':'prepared','components':len(comps),'nets':len(ev.get('nets',{})),'directed_edges':len(ev.get('edges',[])), 'uncertainties':unresolved}

def verify(vsdx, compiled_path):
    vsdx=Path(vsdx); m=read(compiled_path); lock=loadlock(m['source_lock']); ev=lock['snapshot']
    require(m['evidence_sha256']==lock['evidence_sha256'],'Compiled evidence digest mismatch')
    qa=read(vsdx.with_suffix('.qa.json')); cat=catalog()
    require(qa['compiled_sha256']==digest(compiled_path),'Renderer metadata belongs to another compiled model')
    with zipfile.ZipFile(vsdx) as z:
        media=[n for n in z.namelist() if n.startswith('visio/media/')]
        require(not media,'Unexpected embedded media '+str(media))
        page=ET.fromstring(z.read('visio/pages/page1.xml'))
    shapes={s.attrib['ID']:s for s in page.findall('v:Shapes/v:Shape',NS)}
    def cell(s,n):
        e=s.find("v:Cell[@N='"+n+"']",NS)
        return e.attrib.get('V') if e is not None else None
    records={str(c['shape_id']):c for c in qa['components']}
    byid={r['id']:r for r in qa['components']}
    require(all(c['id'] in byid for c in m['components']),'Missing modeled object in QA')
    for sid,r in records.items():
        require(sid in shapes,'Missing shape '+r['id'])
        require(shapes[sid].findtext('v:Data2',namespaces=NS)==r['id'],'Wrong identity '+r['id'])
        require(shapes[sid].findtext('v:Data1',namespaces=NS)==r['type'],'Wrong type '+r['id'])
        for n in ('Width','Height'):
            v=cell(shapes[sid],n)
            if v is not None: require(abs(float(v)-r[n.lower()])<1e-5,'Saved size changed '+r['id'])
    cons=collections.defaultdict(list)
    for c in page.findall('v:Connects/v:Connect',NS):cons[c.attrib['FromSheet']].append(c.attrib)
    seg_by_edge=collections.defaultdict(list)
    for w in qa['wires']:
        sid=str(w['id']); require(sid in shapes,'Missing wire '+sid)
        cs=cons[sid]; require(len(cs)==2,'Wire needs two GlueTo records '+sid)
        ends=[]
        for side,expect in [('BeginX',w['from']),('EndX',w['to'])]:
            found=[c for c in cs if c['FromCell']==side]; require(len(found)==1,'Missing endpoint '+sid)
            c=found[0]; match=re.fullmatch(r'Connections\.([^.]+)\.X',c['ToCell'])
            require(match is not None and c['ToSheet'] in records,'Unknown saved target')
            got=records[c['ToSheet']]['id']+'.'+match[1]; require(got==expect,'Wrong saved pin: '+got+' expected '+expect)
            ends.append(got)
        seg_by_edge[w['edge_id']].append((w,shapes[sid]))
    # Compare endpoints recovered from VSDX to logical model paths, including arrows.
    logical=[]
    for w in m['wires']:
        seq=seg_by_edge.pop(w['id'],[]); require(bool(seq),'Missing logical wire '+w['id'])
        require(seq[0][0]['from']==w['from'] and seq[-1][0]['to']==w['to'],'Logical endpoints changed')
        for i,(record,s) in enumerate(seq):
            if i: require(seq[i-1][0]['to']==record['from'],'Broken route chain')
            begin=int(float(cell(s,'BeginArrow') or 0)); end=int(float(cell(s,'EndArrow') or 0))
            kind=w.get('kind','wire'); arrow=w.get('arrow','end') if kind=='edge' else 'none'
            require((begin!=0)==(arrow=='both' and i==0),'Wrong start arrow')
            require((end!=0)==(arrow in {'end','both'} and i==len(seq)-1),'Wrong end arrow')
        logical.append(w)
    require(not seg_by_edge,'Unmodeled QA wire')
    text=[''.join(t.itertext()).strip() for t in page.findall('.//v:Text',NS)]
    for item in m['labels']+m['components']:
        if item.get('text'): require(item['text'] in text,'Missing editable text '+item['text'])
    for w in m['wires']:
        if w.get('label'): require(w['label'] in text,'Missing branch label '+w['label'])
    # Reject added native electrical artwork, not just known records disappearing.
    known_wires={str(w['id']) for w in qa['wires']}
    for sid,s in shapes.items():
        if sid not in records and sid not in known_wires:
            require(s.findtext('v:Data1',namespaces=NS) in {'annotation','annotation-frame','annotation-arrow','edge-label'},'Unregistered shape '+sid)
    netcheck(m['components'],logical,ev,cat)
    checks=qa.get('layout_findings',[])
    result={'native_connectivity':'passed','inventory':'passed','nets':len(ev.get('nets',{})),
            'directed_edges':len(ev.get('edges',[])),'saved_glued_endpoints':len(qa['wires'])*2,
            'embedded_media':media,'layout_findings':checks,'source_interpretation':'requires_visual_review',
            'uncertainties':ev.get('uncertainties',[]),'vsdx_sha256':digest(vsdx),
            'compiled_sha256':digest(compiled_path),'source_sha256':lock['source_sha256'],
            'scope':'Checks confirm consistency with locked source transcription, not automatic proof of image interpretation.'}
    write(vsdx.with_suffix('.verification.json'),result); return result

def compare(compiled_path, rendered, out):
    from PIL import Image, ImageDraw
    m=read(compiled_path); lock=loadlock(m['source_lock']); ev=lock['snapshot']; out=Path(out); out.mkdir(parents=True,exist_ok=True)
    src=Image.open(lock['source']).convert('RGB'); dst=Image.open(rendered).convert('RGB')
    regions={p['id']:p for p in ev['panels']}; paths=[]
    for p in m['panels']:
        x,y,w,h=regions[p['id']]['bbox']; a=src.crop((x,y,x+w,y+h))
        ox,oy=p['at']; pw,ph=p['size']; sx=dst.width/m['canvas'][0]; sy=dst.height/m['canvas'][1]
        b=dst.crop((int(ox*sx),int(oy*sy),int((ox+pw)*sx),int((oy+ph)*sy)))
        def fit(im):
            factor=min(800/im.width,700/im.height)
            im=im.resize((max(1,round(im.width*factor)),max(1,round(im.height*factor))))
            c=Image.new('RGB',(820,740),'white'); c.paste(im,((820-im.width)//2,30)); return c
        board=Image.new('RGB',(1640,740),'#eeeeee'); board.paste(fit(a),(0,0)); board.paste(fit(b),(820,0)); d=ImageDraw.Draw(board)
        d.text((10,8),'REFERENCE / '+p['id'],fill='black'); d.text((830,8),'REBUILT / '+p['id'],fill='black')
        target=out/(p['id']+'-compare.png'); board.save(target); paths.append(str(target))
        # Normalized overlay is a localization aid only; optimized layouts legitimately differ.
        a.thumbnail((1000,1000)); blend=Image.blend(a,b.resize(a.size),.5); blend.save(out/(p['id']+'-overlay.png'))
    write(out/'review-template.json',{'vsdx_sha256':None,'panels':[{ 'id':p['id'],'status':'pending',
        'checks':{'inventory':'pending','topology':'pending','symbols':'pending','text':'pending','layout':'pending'},
        'findings':[],'resolved_layout_findings':[]} for p in m['panels']]})
    return {'comparison_images':paths,'note':'Inspect images, then fill review; overlays are not pass/fail scores.'}

def finalize(vsdx, compiled, review):
    report=verify(vsdx,compiled); r=read(review); m=read(compiled)
    require(r.get('vsdx_sha256')==digest(vsdx),'Visual review must reference the current VSDX hash')
    panels={p['id']:p for p in r['panels']}; require(set(panels)=={p['id'] for p in m['panels']},'Missing panel review')
    required={'inventory','topology','symbols','text','layout'}
    for p in panels.values():
        require(p.get('status')=='passed' and set(p.get('checks',{}))==required and all(v=='passed' for v in p['checks'].values()),'Incomplete visual review '+p['id'])
        require(not p.get('findings'), 'Unresolved visual findings '+p['id'])
    acknowledged={i for p in panels.values() for i in p.get('resolved_layout_findings',[])}
    require({i['id'] for i in report['layout_findings']}<=acknowledged,'Layout findings need fixes or visual resolutions')
    require(not report['uncertainties'],'Unresolved source uncertainties; deliver a labeled draft, not a complete reproduction')
    report.update(source_interpretation='visually_reviewed',status='complete',visual_review_sha256=digest(review))
    write(Path(vsdx).with_suffix('.verification.json'),report); return report

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('record'); a.add_argument('--evidence',required=True); a.add_argument('--lock',required=True)
    a=sub.add_parser('prepare'); a.add_argument('--model',required=True); a.add_argument('--lock',required=True); a.add_argument('--out',required=True)
    a=sub.add_parser('verify'); a.add_argument('--vsdx',required=True); a.add_argument('--compiled',required=True)
    a=sub.add_parser('compare'); a.add_argument('--compiled',required=True); a.add_argument('--rendered',required=True); a.add_argument('--out',required=True)
    a=sub.add_parser('finalize'); a.add_argument('--vsdx',required=True); a.add_argument('--compiled',required=True); a.add_argument('--review',required=True)
    a=p.parse_args()
    if a.command=='record': result=record(a.evidence,a.lock)
    elif a.command=='prepare': result=prepare(a.model,a.lock,a.out)
    elif a.command=='verify': result=verify(a.vsdx,a.compiled)
    elif a.command=='compare': result=compare(a.compiled,a.rendered,a.out)
    else: result=finalize(a.vsdx,a.compiled,a.review)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr,'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
    try: main()
    except (ValueError,KeyError) as e:
        print('ERROR: '+str(e),file=sys.stderr); sys.exit(1)
