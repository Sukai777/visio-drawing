"""Meaningful negative tests of preflight and saved VSDX; requires rendered examples."""
import argparse
import copy
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import drawing as d

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--outputs',required=True,help='Folder holding small-signal, flow and lr-branches VSDX/compiled/QA files')
    parser.add_argument('--report',required=True)
    args=parser.parse_args(); outputs=Path(args.outputs); results=[]
    def rejected(name,operation,contains):
        try: operation()
        except ValueError as e:
            if contains not in str(e): raise AssertionError(f'{name}: unexpected failure {e}')
            results.append({'test':name,'status':'rejected_as_expected','message':str(e)})
        else: raise AssertionError('Invalid case accepted: '+name)
    with tempfile.TemporaryDirectory(prefix='visio-drawing-regression-') as tmp:
        tmp=Path(tmp)
        def compile_case(name,example,change,contains):
            m=d.read(d.ROOT/'examples'/f'{example}.model.json');change(m)
            p=tmp/(name+'.json');d.write(p,m)
            compiled=d.read(outputs/(example+'.compiled.json'))
            rejected(name,lambda:d.prepare(p,compiled['source_lock'],tmp/(name+'.compiled.json')),contains)
        compile_case('gate_drain_short','small-signal',lambda m:m['wires'].append({'from':'CGS.A','to':'GM.A'}),'Short between')
        compile_case('added_capacitor','small-signal',lambda m:m['components'].append({'id':'C_FAKE','type':'capacitor','panel':'c','at':[10,10]}),'Inventory mismatch')
        compile_case('missing_resistor','small-signal',lambda m:m['components'].remove(next(c for c in m['components'] if c['id']=='RDS')),'Inventory mismatch')
        compile_case('stretch_symbol','small-signal',lambda m:m['components'][3].update(w=999),'never independent w/h')
        compile_case('unexplained_scale','small-signal',lambda m:m['components'][3].update(size=5),'requires source/layout reason')
        compile_case('lr_lower_end_open','lr-branches',lambda m:m['wires'].remove(next(w for w in m['wires'] if w['from']=='R16.B')),'Open expected net')
        compile_case('wrong_type','small-signal',lambda m:next(c for c in m['components'] if c['id']=='G_OUT').update(type='capacitor'),'Type/panel mismatch')
        compile_case('reverse_flow','flow',lambda m:m['wires'][0].update({'from':'READ.T','to':'START.B'}),'Directed edge/branch-label mismatch')
        compile_case('wrong_branch_label','flow',lambda m:m['wires'][2].update(label='No'),'Directed edge/branch-label mismatch')
        compile_case('wrong_parent','flow',lambda m:m['components'][1].update(parent=None),'Container ownership mismatch')
        compile_case('source_as_annotation','small-signal',lambda m:m['components'].remove(next(c for c in m['components'] if c['id']=='GM')),'Inventory mismatch')
        compile_case('unknown_terminal','small-signal',lambda m:m['wires'][0].update(to='CGS.G'),'Unknown endpoint')
        compile_case('electrical_arrow','small-signal',lambda m:m['wires'][0].update(arrow='end'),'Electrical wires cannot')
        compile_case('missing_visible_junction','small-signal',lambda m:m['nodes'].pop(),'Visible junction inventory mismatch')
        compile_case('semantic_color_changed','flow',lambda m:m['components'][1].update(fill='#ff0000'),'Source color role mismatch')
        locked=d.read(d.read(outputs/'small-signal.compiled.json')['source_lock'])
        altered_ev=tmp/'altered-source.json';d.write(altered_ev,locked['snapshot'])
        locked['evidence']=str(altered_ev)
        locked['evidence_sha256']='0'*64
        altered_lock=tmp/'altered.lock.json';d.write(altered_lock,locked)
        rejected('changed_source_evidence',lambda:d.loadlock(altered_lock),'Evidence changed after recording')
        # Positive calibration: body width must be respected, with proportional height.
        m=d.read(d.ROOT/'examples/small-signal.model.json');m['styles']['resistor']={'body_width':24}
        p=tmp/'body.json';d.write(p,m);comp=outputs/'small-signal.compiled.json'
        d.prepare(p,d.read(comp)['source_lock'],tmp/'body.compiled.json')
        calibrated=next(c for c in d.read(tmp/'body.compiled.json')['components'] if c['id']=='RDS')
        assert abs(calibrated['w']*.8-24)<1e-9
        results.append({'test':'measured_body_size','status':'passed'})
        # Ground domains must not accidentally short otherwise separate diagrams.
        cats=d.catalog(); cs=[{'id':'GA','type':'ground','ground_domain':'analog'},{'id':'GB','type':'ground','ground_domain':'digital'}]
        d.netcheck(cs,[],{'nets':{'a':['GA.P'],'b':['GB.P']},'must_separate':[['GA.P','GB.P']]},cats)
        results.append({'test':'separate_ground_domains','status':'passed'})
        def mutate_saved(name,example,change,contains):
            original=outputs/(example+'.vsdx');target=tmp/(name+'.vsdx')
            qa=d.read(original.with_suffix('.qa.json'))
            with zipfile.ZipFile(original) as z:
                page=ET.fromstring(z.read('visio/pages/page1.xml'));change(page,qa)
                with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as out:
                    for info in z.infolist():out.writestr(info,z.read(info.filename) if info.filename!='visio/pages/page1.xml' else ET.tostring(page,encoding='utf-8',xml_declaration=True))
            d.write(target.with_suffix('.qa.json'),qa)
            rejected(name,lambda:d.verify(target,outputs/(example+'.compiled.json')),contains)
        def lose_glue(page,qa):
            cons=page.find('v:Connects',d.NS);cons.remove(list(cons)[0])
        mutate_saved('deleted_saved_glue','small-signal',lose_glue,'two GlueTo records')
        def redirect(page,qa):
            con=page.find('v:Connects/v:Connect',d.NS);con.set('ToCell','Connections.T.X')
        mutate_saved('redirected_saved_pin','small-signal',redirect,'Wrong saved pin')
        def remove_source(page,qa):
            sid=str(next(r for r in qa['components'] if r['id']=='GM')['shape_id'])
            shapes=page.find('v:Shapes',d.NS);shapes.remove(next(s for s in shapes if s.attrib['ID']==sid))
        mutate_saved('deleted_current_source','small-signal',remove_source,'Missing shape GM')
        def remove_arrow(page,qa):
            sid=str(qa['wires'][0]['id']);s=next(s for s in page.find('v:Shapes',d.NS) if s.attrib['ID']==sid)
            cell=s.find("v:Cell[@N='EndArrow']",d.NS);cell.set('V','0');cell.attrib.pop('F',None)
        mutate_saved('missing_flow_arrow','flow',remove_arrow,'Wrong end arrow')
        def resize(page,qa):
            sid=str(next(r for r in qa['components'] if r['id']=='RDS')['shape_id'])
            s=next(s for s in page.find('v:Shapes',d.NS) if s.attrib['ID']==sid)
            cell=s.find("v:Cell[@N='Width']",d.NS);cell.set('V','5');cell.attrib.pop('F',None)
        mutate_saved('saved_symbol_size_changed','small-signal',resize,'Saved size changed')
        def unregistered(page,qa):
            shapes=page.find('v:Shapes',d.NS);extra=ET.SubElement(shapes,'{'+d.NS['v']+'}Shape',{'ID':'999999'})
            ET.SubElement(extra,'{'+d.NS['v']+'}Data1').text='resistor'
        mutate_saved('unregistered_electrical_artwork','small-signal',unregistered,'Unregistered shape')
        empty=tmp/'empty-review.json';d.write(empty,{'vsdx_sha256':'stale','panels':[]})
        rejected('stale_visual_review',lambda:d.finalize(outputs/'small-signal.vsdx',outputs/'small-signal.compiled.json',empty),'current VSDX hash')
        report={'status':'passed','tests':len(results),'results':results}
        d.write(args.report,report);print(f"Passed {len(results)} regression cases")

if __name__=='__main__':main()
