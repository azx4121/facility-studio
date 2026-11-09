"""Require real native positive and foreign-image-negative Job audit receipts."""
import argparse,json,ntpath
from pathlib import Path
import xml.etree.ElementTree as ET
EXPECTED={'test_native_child_identity[False]':'allowed','test_native_child_identity[True]':'denied'}
def require(ok,message):
    if not ok:raise ValueError(message)
def pairs(rows):
    result={}
    for k,v in rows:
        require(k not in result,'Duplicate JSON key');result[k]=v
    return result
def normal(path):return ntpath.normcase(ntpath.normpath(path))
def verify(path):
    raw=path;require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw,'Unsafe JUnit')
    root=ET.fromstring(raw);suites=list(root.iter('testsuite'));cases=list(root.iter('testcase'))
    require(len(suites)==1 and len(cases)==2 and {c.get('name') for c in cases}==set(EXPECTED),'Exact two native image controls required')
    require(suites[0].get('tests')=='2' and all(suites[0].get(k)=='0' for k in ('errors','failures','skipped')),'JUnit aggregate mismatch')
    for case in cases:
        require(case.get('classname','').endswith('test_standalone_process_images') and not any(case.find(k) is not None for k in ('failure','error','skipped')),'Native image control failed or skipped')
        props=case.findall('./properties/property[@name="process_image_preflight"]');require(len(props)==1,'Missing or duplicate image preflight receipt')
        data=json.loads(props[0].get('value'),object_pairs_hook=pairs);expected=EXPECTED[case.get('name')]
        require(type(data.get('schema_version')) is int and data['schema_version']==1 and data.get('expected')==expected and data.get('passed') is True,'Wrong image control identity')
        command=data.get('command');require(isinstance(command,list) and command and isinstance(command[0],str) and ntpath.isabs(command[0]),'Invalid root image')
        base,controller=data.get('synthetic_base_executable'),data.get('synthetic_controller_executable')
        require(isinstance(base,str) and ntpath.isabs(base) and normal(base)==normal(command[0])
                and isinstance(controller,str) and ntpath.isabs(controller),'Synthetic control did not identify its absolute base interpreter')
        audit=data.get('process_image_audit');require(isinstance(audit,dict) and audit.get('required') is True,'Missing required process audit')
        images=audit.get('images');require(isinstance(images,list) and images and all(isinstance(r,dict) and type(r.get('pid')) is int and r['pid']>0 and isinstance(r.get('image'),str) and ntpath.isabs(r['image']) for r in images),'Missing process images')
        require(type(audit.get('total_job_processes')) is int and type(audit.get('retained_process_handles')) is int and audit['total_job_processes']==audit['retained_process_handles']==len(images)==len({r['pid'] for r in images}),'Incomplete process coverage')
        same=[normal(r['image'])==normal(command[0]) for r in images]
        if expected=='allowed':
            require(audit.get('passed') is True and audit.get('errors')==[] and len(images)==2 and all(same),'Same-image positive control failed')
        else:
            errors=audit.get('errors')
            require(audit.get('passed') is False and isinstance(errors,list) and errors
                    and all(isinstance(e,str) and e.startswith('Unexpected external process image: ') for e in errors)
                    and any(same) and not all(same),'Foreign-image control failed for wrong reason')
    return dict(native_process_image_controls=2,allowed_same_image=True,rejected_external_image=True,zero_skips=True,passed=True)
