"""Exact UI newline serialization only; no arbitrary text normalization."""
import copy
import tempfile
import unittest
from pathlib import Path
import publish_verified_windows as p
from test_publication import Fixture, FakeClient

class OwnerBodySerializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name));self.final=p.FinalRelease(self.f.lock)
    def row(self,body,draft=True):
        return dict(id=402,draft=draft,tag_name=self.final.tag,target_commitish=self.final.commit,
            name=self.final.name,body=body,prerelease=False,
            published_at=None if draft else '2026-11-08T00:00:00Z',
            html_url=p.WEB+'/releases/tag/'+('untagged-402' if draft else self.final.tag))
    def test_exact_lf_and_crlf_accepted_draft_and_public(self):
        for draft in (False,True):
            for body in (self.final.body,self.final.body.replace('\n','\r\n')):
                with self.subTest(draft=draft,crlf='\r' in body):self.final.metadata(self.row(body,draft),402,draft)
    def test_other_serializations_rejected_draft_and_public(self):
        body=self.final.body
        values=[None,True,{},body.replace('\n','\r\n',1),body.replace('\n','\r'),
            body+' ',body+'\n',' '+body,body[:-1],body.replace('\n','\r\r\n'),
            body.replace('Windows','Changed',1)]
        for draft in (False,True):
            for value in values:
                with self.subTest(draft=draft,value=repr(value)[:30]),self.assertRaises(p.GateError):
                    self.final.metadata(self.row(value,draft),402,draft)
    def test_crlf_does_not_relax_other_metadata(self):
        original=self.row(self.final.body.replace('\n','\r\n'))
        for key,value in dict(id=999,draft=False,tag_name='other',target_commitish='0'*40,name='other',prerelease=True,published_at='now').items():
            row=dict(original,**{key:value})
            with self.subTest(key=key),self.assertRaises(p.GateError):self.final.metadata(row,402,True)
    def test_stage_crlf_draft_uploads_only_and_stays_draft(self):
        c=FakeClient(self.f);c.releases[402]=self.row(self.final.body.replace('\n','\r\n'))
        self.final.before_write=lambda:None
        files=p.prepare_payloads(c,self.f.lock,self.f.gate(),Path(self.tmp.name)/'payload')
        self.final.stage_existing(c,402,files,self.f.gate)
        writes=[(m,u) for m,u,a in c.calls if m in {'POST','PATCH','DELETE','PUT'}]
        self.assertEqual(len(writes),3)
        self.assertTrue(all(m=='POST' and u.startswith(p.UPLOADS+'/releases/402/assets?') for m,u in writes))
        self.assertTrue(c.releases[402]['draft'])
