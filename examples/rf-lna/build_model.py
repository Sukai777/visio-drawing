import json
from pathlib import Path
P=Path(__file__).parent
e=json.loads((P/'source.json').read_text(encoding='utf-8'))
panels=[{'id':p['id'],'at':p['bbox'][:2],'size':p['bbox'][2:]} for p in e['panels']]
offset={'input_feedback':0,'core_stability':520,'output_bias':995}
inv={c['id']:c for c in e['inventory']}
comps=[]; nodes=[]; wires=[]; labels=[]; anns=[]
def c(id,x,y,rot=0,anchor=None,**kw):
 p=inv[id]['panel'];d=dict(id=id,type=inv[id]['type'],panel=p,at=[x-offset[p],y],rotate=rot,weight=2.0,color='#080808')
 if anchor:d['anchor']=anchor
 d.update(kw);comps.append(d);return d
def n(id,x,y):
 p=next(j['panel'] for j in e['junctions'] if j['id']==id)
 nodes.append(dict(id=id,panel=p,at=[x-offset[p],y],diameter=5,color='#111111'))
def w(a,b,via=None,route='hv',color='#111111'):
 d=dict(id='w'+str(len(wires)+1),**{'from':a,'to':b},kind='wire',route=route,weight=1.2,color=color)
 if via:d.update(panel='input_feedback',via=via)
 wires.append(d)
def joins(node,ends):
 for ep in ends.split():w(ep,node+'.P')
def lab(text,x,y,width=65,height=28,fs=19,color='#080808',runs=None):
 p='input_feedback' if x<520 else 'core_stability' if x<995 else 'output_bias'
 if runs is None:
  special={'M0_1':('M','0_1'),'M0_2':('M','0_2'),'RFin':('RF','in'),'RFout':('RF','out'),'VDD':('V','DD'),'Cvgc':('C','vgc'),'RLER':('R','LER'),'IM1':('I','M1'),'ILER':('I','LER')}
  if text in special:
   a,b=special[text];runs=[{'text':a},{'text':b,'sub':True}]
  else:
   for pre in ('TL','R','L','C','M'):
    if text.startswith(pre) and text[len(pre):].isdigit():runs=[{'text':pre},{'text':text[len(pre):],'sub':True}];break
 d=dict(panel=p,at=[x-offset[p],y],w=width,h=height,font_size=fs,style=3,color=color,text=text)
 if runs:d['runs']=runs
 labels.append(d)
def frame(x,y,width,height,color,purpose):
 anns.append(dict(kind='frame',panel='input_feedback',at=[x,y],w=width,h=height,fill=color,color=color,purpose=purpose,rounding=12 if width<300 else 0))
def arrow(points,color,purpose):anns.append(dict(kind='arrow',panel='input_feedback',points=points,color=color,purpose=purpose))

# Calibrated bodies, centered at the measured source positions.
c('M0_1',119,80,180,'G',profile='biasmos')
c('G_M0_1',81.5,49,180,'P')
c('M0_2',811,623,0,'G',flip_x=True,profile='biasmos')
c('G_M0_2',773.5,650,0,'P')
for id,x,y in [('M1',220,389),('M2',556,356),('M4',1266,356)]:c(id,x,y,anchor='G')
c('M3',888,324,anchor='G',flip_y=True)
for id,x,y in [('R1',114,139),('R2',237,80),('R4',371,80),('R6',495,120),('R8',630,80),('R7',508,237),('R9',484,471),('R14',927,444),('R18',1220,303),('R10',806,565),('R12',898,623),('R13',988,623),('R21',1069,623),('R20',1420,567)]:c(id,x,y,90)
for id,x,y in [('R3',304,154),('R5',452,161),('R17',823,110),('R16',1063,219),('R19',1405,145),('R11',778,497),('R15',1188,497),('RLER',660,502)]:c(id,x,y)
for id,x,y in [('C1',79,389),('C2',162,279),('C3',412,356),('C4',568,237),('C5',552,120),('C6',735,324),('C9',1155,356),('C10',1220,356),('C12',1435,324),('C13',1357,567)]:c(id,x,y,90)
for id,x,y in [('Cvgc',606,505),('C7',872,392),('C8',934,110),('C11',823,153)]:c(id,x,y)
for id,x,y in [('L1',117,334),('L3',698,156),('L4',1063,149),('L5',1405,217)]:c(id,x,y)
c('L2',389,471,90)
for id,x,y in [('TL1',171,389),('TL3',348,356),('TL5',506,356),('TL7',652,324),('TL8',637,237),('TL9',818,324),('TL14',1018,356),('TL15',1105,356),('TL17',1356,324),('TL10',894,536),('TL11',1097,536)]:c(id,x,y)
for id,x,y in [('TL2',270,458),('TL4',452,305),('TL6',606,426),('TL12',937,245),('TL13',973,394),('TL16',1316,416),('TL18',1470,514)]:
 d=c(id,x,y,270)
 if id in ['TL2','TL6','TL12','TL16']:
  target={'TL2':'M1.S','TL6':'M2.S','TL12':'M3.S','TL16':'M4.S'}[id]
  d['anchor']='A';d['at'][1]-=25;d['align']={'x':target}
for id,x,y,rot in [('G_C2',180,279,90),('G_C5',573,120,90),('G_C13',1336,567,270),('G_M1',270,501,0),('G_Cvgc',606,531,0),('G_RLER',660,531,0),('G_C8',934,135,0),('G_C11',823,175,0),('G_TL12',937,216,180),('G_M4',1316,443,0)]:c(id,x,y,rot,'P')
c('RF_IN',39,389);c('RF_OUT',1494,324)
for j in e['junctions']:
 x,y,ww,hh=j['bbox'];n(j['id'],x+ww/2,y+hh/2)
# Correct dot locations to the source stroke centers.
for nn in nodes:
 if nn['id']=='J_IMN':nn['at']=[117,389]
 if nn['id']=='J_IMN_TOP':nn['at']=[117,279]
 if nn['id']=='J_VGC':nn['at']=[606-offset[nn['panel']],471]
for ident,x,y in [('VDD_TOP',698,64),('VDD_LEFT',686,64),('VDD_RIGHT',710,64)]:
 nodes.append(dict(id=ident,panel='core_stability',at=[x-520,y],diameter=.1,hidden=True))
w('J_VDD.P','VDD_TOP.P');w('VDD_LEFT.P','VDD_TOP.P',color='#595959');w('VDD_TOP.P','VDD_RIGHT.P',color='#595959')

# Bias and common ground branches. These routes follow the frozen source nets.
for a,b in [('M0_1.S','G_M0_1.P'),('M0_2.S','G_M0_2.P'),('TL2.B','G_M1.P'),('TL6.B','J_VGC.P'),('Cvgc.B','G_Cvgc.P'),('RLER.B','G_RLER.P'),('C11.B','G_C11.P'),('C8.B','G_C8.P'),('TL12.A','G_TL12.P'),('TL16.B','G_M4.P'),('C2.B','G_C2.P'),('C5.B','G_C5.P'),('C13.A','G_C13.P')]:w(a,b,route='vh')
joins('J_SUP0','M0_1.G R1.B R2.A')
w('M0_1.D','R1.A',via=[[81.5,139]])
joins('J_R2','R2.B R3.A R4.A')
joins('J_R4','R4.B R8.A')
w('J_R4.P','J_R6.P');joins('J_R6','R5.A R6.A')
w('R6.B','C5.A')
w('R8.B','J_VDD.P');w('L3.A','J_VDD.P')
for a,b in [('J_VDD.P','J_R17.P'),('J_R17.P','J_C8.P'),('J_C8.P','J_L4.P'),('J_L4.P','J_R19.P')]:w(a,b)
for a,b in [('R17.A','J_R17.P'),('C8.A','J_C8.P'),('L4.A','J_L4.P'),('R19.A','J_R19.P'),('R17.B','C11.A'),('L4.B','R16.A'),('R19.B','L5.A')]:w(a,b)
w('J_R19.P','TL18.A',via=[[1470,80]])
w('R3.B','J_IMN_TOP.P',via=[[304,229],[117,229]],route='vh')

# Input, two common-source stages, feedback and current reuse.
w('RF_IN.B','C1.A');joins('J_IMN','C1.B L1.B TL1.A');joins('J_IMN_TOP','L1.A C2.A')
w('TL1.B','M1.G');w('M1.S','TL2.A',route='vh')
w('M1.D','J_M1_D.P',route='vh');w('J_M1_D.P','TL3.A')
w('J_M1_D.P','L2.A',via=[[311,471]])
w('TL3.B','C3.A');joins('J_FB_MAIN','C3.B TL5.A TL4.B')
joins('J_FB_LEFT','R5.B TL4.A R7.A')
w('TL5.B','M2.G');w('M2.S','TL6.A',route='vh')
w('L2.B','R9.A');w('R9.B','J_VGC.P');joins('J_VGC','Cvgc.A RLER.A')
w('M2.D','TL7.A',route='vh');joins('J_M2_OUT','TL7.B C6.A')
joins('J_FB_OUT','L3.B TL8.B');w('J_FB_OUT.P','J_M2_OUT.P')
w('R7.B','C4.A');w('C4.B','TL8.A')
joins('J_C6_OUT','C6.B TL9.A');w('J_C6_OUT.P','R11.A')

# Common-gate M3: source points upwards. C7-R14-TL13 is a series branch.
joins('J_M3_GATE','TL9.B M3.G C7.A')
w('M3.S','TL12.B',route='vh')
w('M3.D','J_M3_SOURCE.P',route='vh')
joins('J_M3_SOURCE','TL13.A TL14.A')
w('C7.B','R14.A',via=[[872,444]],route='vh')
w('R14.B','TL13.B',via=[[973,444]])

# LR shunts, RC parallel element and final output.
joins('J_LR_LEFT','TL14.B TL15.A R16.B')
w('TL15.B','C9.A');joins('J_RC_LEFT','C9.B C10.A R18.A R15.A')
joins('J_RC_RIGHT','C10.B R18.B M4.G')
w('M4.D','TL17.A',route='vh');w('M4.S','TL16.A',route='vh')
joins('J_RF_OUT','TL17.B C12.A L5.B');w('C12.B','RF_OUT.A')

# Lower bias loop; vertical outer supply bus crosses the RF output without joining it.
w('R11.B','TL10.A',via=[[778,536]],route='vh')
joins('J_BOT_B','R12.B R13.A');w('TL10.B','J_BOT_B.P',via=[[945,536]])
joins('J_BOT_A','R12.A M0_2.G');w('R10.B','J_BOT_A.P',via=[[846,565]])
w('R10.A','M0_2.D',via=[[773.5,565]])
joins('J_BOT_C','R13.B R21.A');w('TL11.A','J_BOT_C.P',via=[[1029,536]])
w('TL11.B','R15.B',via=[[1188,536]])
w('R21.B','J_R20.P',via=[[1470,623]])
joins('J_R20','TL18.B R20.B');w('R20.A','C13.B')

# Source component text remains separate editable text with native subscripts.
specs=[
('M0_1',27,64),('R1',96,153),('R2',220,92),('R3',262,140),('R4',357,92),('R5',408,146),('R6',478,133),('C5',537,133),('R8',617,92),
('L1',73,321),('C1',65,406),('C2',146,295),('TL1',147,405),('M1',271,373),('TL2',208,445),('TL3',324,373),('C3',396,373),('TL4',395,290),('TL5',482,373),
('R7',492,250),('C4',554,250),('TL8',614,250),('L2',373,487),('R9',471,487),('M2',600,339),('TL6',545,412),('TL7',632,339),('Cvgc',545,488),('RLER',675,488),
('L3',654,142),('R17',771,96),('C11',769,142),('C8',889,96),('C6',722,339),('TL9',793,339),('M3',938,308),('TL12',870,231),('TL13',908,376),('C7',825,377),('R14',908,408),('TL14',992,373),
('L4',1016,137),('R16',1013,205),('TL15',1081,373),('C9',1140,373),('C10',1204,373),('R18',1201,268),('M4',1306,339),('TL16',1330,405),('TL17',1330,286),('R19',1355,137),('L5',1358,205),('C12',1415,339),
('R11',791,480),('R10',787,575),('M0_2',737,607),('TL10',870,547),('R12',880,636),('R13',971,636),('R21',1053,636),('TL11',1072,547),('R15',1137,480),('TL18',1405,507),('R20',1403,580),('C13',1341,580)]
gray={'M0_1','R1','R2','R3','R4','R5','R6','C5','R8','L3','R17','C11','C8','R11','R10','M0_2','TL10','R12','R13','R21','TL11','R15','TL18','R20','C13'}
for s,x,y in specs:
 if s=='R14':y=403
 if s=='R18':y=262
 if s=='R10':y=573
 lab(s,x,y,color='#595959' if s in gray else '#080808')
for co in comps:
 if co['id'] in gray or co['id'] in ['G_M0_1','G_M0_2','G_C5','G_C11','G_C8','G_C13']:co['color']='#595959'
lab('RFin',15,344,75);lab('RFout',1449,276,77)
lab('VDD',680,34,66,color='#595959')
lab('Bias Network',378,24,190,color='#595959')
lab('Bias Network',1243,645,200,color='#595959')
lab('R-L-C Feedback',486,192,215,color='#9e392f')
lab('T-type IMN',73,438,165,color='#8063a6')
lab('Current-Reuse',385,521,125,57,color='#516a30',runs=[{'text':'Current-'},{'text':'Reuse'}])
lab('IM1',306,477,63);lab('ILER',639,439,72)
lab('VGC',556,556,82,color='#9e392f');lab('LER',651,556,72,color='#b68b00')
lab('Stability Enhancement Circuit',976,264,174,78,17,'#238aa3')
lab('LR Circuit',1166,171,180,color='#e96100')
lab('RC Circuit',1195,216,70,54,17,'#238aa3')
lab('M0_1, M0_2: 2×25 μm',49,610,330,38,runs=[{'text':'M'},{'text':'0_1','sub':True},{'text':', M'},{'text':'0_2','sub':True},{'text':': 2×25 μm'}])

# Highlights first; renderer sends each successive background farther back.
for args in [(64,261,143,173,'#dcd4e6','T-type IMN'),(481,218,191,62,'#d88e89','R-L-C Feedback'),(350,450,167,66,'#c7d7a1','Current reuse'),(542,474,88,83,'#d88e89','VGC'),(632,440,93,117,'#ffe495','LER'),(823,359,170,99,'#b4dce5','Stability feedback'),(1181,268,79,130,'#b4dce5','Parallel RC'),(1011,122,74,125,'#ef6c00','Left LR'),(1349,122,79,125,'#ef6c00','Right LR')]:frame(*args)
arrow([[1164,185],[1085,185]],'#ef6c00','LR left callout');arrow([[1290,185],[1349,185]],'#ef6c00','LR right callout')
arrow([[978,307],[907,358]],'#238aa3','Stability feedback callout');arrow([[1105,305],[1181,331]],'#238aa3','Parallel RC callout')
arrow([[350,471],[311,471]],'#111111','M1 current direction');arrow([[607,471],[658,471]],'#111111','LER current direction')
frame(16,18,962,175,'#f0f0f0','Upper bias network')
frame(735,471,775,212,'#f0f0f0','Lower bias network')
frame(16,18,1494,665,'#fcebdc','RF circuit page background')
model=dict(version=2,canvas=[1535,694],inches_per_unit=.012,font='Times New Roman',panels=panels,styles={
 'resistor':{'span':60,'aspect':.44,'source_reason':'Reference resistor body about 32 by 21 pixels'},
 'capacitor':{'span':34,'aspect':.85,'source_reason':'Reference plates about 29 pixels with short fixed leads'},
 'inductor':{'span':64,'aspect':.43,'source_reason':'Reference coil body about 43 by 28 pixels'},
 'nmos':{'span':66},'biasmos':{'span':50},'line_section':{'span':50},'ground':{'span':26},'pad':{'span':12}
},components=comps,nodes=nodes,wires=wires,labels=labels,annotations=anns,transform_test_ids=['M0_1','M0_2','M3','C1','L2','TL13'])
(P/'model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
print('Model:',len(comps),'components,',len(wires),'routes')
