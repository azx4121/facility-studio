import copy
import pytest
from run_frozen_cli import valid_process_image_audit

def good():
    return dict(required=True, passed=True, errors=[], total_job_processes=2,
                retained_process_handles=2, images=[dict(pid=10,image='app.exe'),dict(pid=11,image='app.exe')])

def test_valid_audit():
    assert valid_process_image_audit(good())

@pytest.mark.parametrize('field,value', [('required',False),('passed',False),('errors',['query failed']),
    ('total_job_processes',0),('total_job_processes',True),('retained_process_handles',1),
    ('images',[]),('images',[dict(pid=10,image='app.exe'),dict(pid=10,image='app.exe')]),
    ('images',[dict(pid=10,image=''),dict(pid=11,image='app.exe')])])
def test_invalid_audit(field,value):
    audit=good();audit[field]=value
    assert not valid_process_image_audit(audit)

@pytest.mark.parametrize('audit', [None,{},False])
def test_missing_audit(audit):
    assert not valid_process_image_audit(audit)

def test_receipt_bound_to_expected_image():
    assert valid_process_image_audit(good(), 'APP.EXE')
    assert not valid_process_image_audit(good(), 'python.exe')
