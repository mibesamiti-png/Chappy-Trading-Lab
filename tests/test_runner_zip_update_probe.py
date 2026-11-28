"""Synthetic HTTP response tests; never access the network in CI."""
import ast
import json
from pathlib import Path
import re
import time
import urllib.request
import urllib.error
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'update_version_tuple','update_manifest_version','update_probe','update_probe_text'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
       isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('UPDATE_') for t in n.targets)]
scope=dict(json=json,re=re,time=time,urllib=urllib)
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),scope)

class FakeResponse:
    def __init__(self,url,raw,status=200):
        self.url,self.raw,self.status=url,raw,status
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def geturl(self): return self.url
    def read(self,n): return self.raw[:n]

class UpdateProbeTests(unittest.TestCase):
    def manifest(self,version):
        return json.dumps(dict(schema=1,scope='SYNTHETIC_ONLY',min_launcher=1,version=version,
                               files={name:'a'*64 for name in scope['UPDATE_FILE_NAMES']})).encode()

    def response(self,version,status=200):
        def opener(request,timeout):
            self.assertEqual(timeout,8)
            self.assertTrue(request.full_url.startswith(scope['UPDATE_MANIFEST_URL']+'?ctl_check='))
            self.assertIsNone(request.get_header('Authorization'))
            return FakeResponse(request.full_url,self.manifest(version),status)
        return opener

    def test_versions_and_interval(self):
        for remote,expected in [('0.8.10','NEWER'),('0.8.8','SAME'),('0.8.7','REMOTE_OLDER')]:
            result=scope['update_probe']('0.8.8',self.response(remote))
            self.assertEqual(result['code'],expected)
            self.assertEqual(result['http'],200)
            self.assertEqual(result['remote'],remote)
        self.assertEqual(scope['UPDATE_INTERVAL_MS'],120000)

    def test_errors_are_not_latest(self):
        def offline(*args,**kwargs):
            raise urllib.error.URLError('PRIVATE_NETWORK_DETAIL')
        result=scope['update_probe']('0.8.8',offline)
        self.assertEqual(result['code'],'FAILED_CONNECTION')
        self.assertIn('最新状態未確認',scope['update_probe_text'](result))
        self.assertNotIn('PRIVATE_NETWORK_DETAIL',scope['update_probe_text'](result))
        result=scope['update_probe']('0.8.8',self.response('bad'))
        self.assertEqual(result['code'],'FAILED_MANIFEST')
        self.assertIsNone(result['remote'])

    def test_redirect_and_bad_response(self):
        def redirect(request,timeout):
            return FakeResponse('https://example.invalid',self.manifest('0.9.0'))
        self.assertEqual(scope['update_probe']('0.8.8',redirect)['code'],'FAILED_MANIFEST')
        self.assertEqual(scope['update_probe']('0.8.8',self.response('0.9.0',500))['code'],'FAILED_MANIFEST')

    def test_scope_and_hash(self):
        raw=json.loads(self.manifest('0.8.8'))
        raw['scope']='REAL'
        with self.assertRaises(ValueError):
            scope['update_manifest_version'](json.dumps(raw).encode())
        raw['scope']='SYNTHETIC_ONLY'
        raw['files']['START_GUI.pyw']='not a hash'
        with self.assertRaises(ValueError):
            scope['update_manifest_version'](json.dumps(raw).encode())

if __name__=='__main__':
    unittest.main()
