import io, json, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Helper"))
import updater as u

REPO='example/ebonupdater'
NAME='EbonUpdater'
def toc(v='0.1.0', repo=REPO):
    return f'## Version: {v}\n## X-GitHub: {repo}\n'
def archive(v='0.1.1', extra=(), repo=REPO):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr(f'{NAME}/{NAME}.toc',toc(v,repo))
        z.writestr(f'{NAME}/Core.lua','-- new')
        for p in extra: z.writestr(p,'bad')
    return stream.getvalue()

class Tests(unittest.TestCase):
    def test_versions(self):
        self.assertGreater(u.version('1.10.0'),u.version('1.9.9'))
        for value in ['01.0.0','1.2','1.2.3-beta','1.2.1234567','v1.0.0']:
            with self.assertRaises(ValueError): u.version(value)
    def test_manifest(self):
        data={'date':'2026-11-24','message':'EBONUPDATER1;EbonUpdater=Example/EbonUpdater,0.1.1'}
        self.assertEqual(u.parse_manifest(data),{'ebonupdater':(REPO,'0.1.1')})
        for msg in ['hello','EBONUPDATER1;','EBONUPDATER1;EbonUpdater=OWNER/EbonUpdater,0.1.1',data['message']+';'+data['message'].split(';')[1]]:
            with self.assertRaises(ValueError): u.parse_manifest(dict(data,message=msg))
    def test_discovery_and_install(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'Interface'/'AddOns'; addon=root/NAME; addon.mkdir(parents=True)
            (addon/(NAME+'.toc')).write_text(toc()); (addon/'Legacy.lua').write_text('old')
            wtf=Path(t)/'WTF'; wtf.mkdir(); (wtf/'settings').write_text('keep')
            self.assertEqual(u.discover(root)['ebonupdater'],(addon,REPO,'0.1.0'))
            backup=u.install_one(root,addon,REPO,'0.1.1',archive(),lambda:None)
            self.assertFalse((addon/'Legacy.lua').exists()); self.assertTrue((backup/'Legacy.lua').exists())
            self.assertEqual((wtf/'settings').read_text(),'keep'); self.assertEqual(u.metadata(addon/(NAME+'.toc'))['version'],'0.1.1')
    def test_invalid_archives(self):
        for data in [archive(extra=['../evil']), archive(extra=[NAME+'/../evil']),archive(extra=[NAME+'/CON.txt']), archive(extra=[NAME+'/core.lua']), archive(extra=['Other/Core.lua']),archive(repo='evil/repo'),archive(v='9.0.0')]:
            with tempfile.TemporaryDirectory() as t:
                with self.assertRaises(ValueError): u.extract(data,Path(t),NAME,REPO,'0.1.1')
    def test_link_archive(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            info=zipfile.ZipInfo(NAME+'/link'); info.create_system=3; info.external_attr=0o120777<<16; z.writestr(info,'elsewhere')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError): u.extract(b.getvalue(),Path(t),NAME,REPO,'0.1.1')
    def test_rollback(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'AddOns'; addon=root/NAME; addon.mkdir(parents=True); (addon/(NAME+'.toc')).write_text(toc())
            original=Path.rename
            def fail_stage(path,dest):
                if '.stage-' in str(path): raise OSError('simulated failure')
                return original(path,dest)
            with patch.object(Path,'rename',fail_stage):
                with self.assertRaises(OSError): u.install_one(root,addon,REPO,'0.1.1',archive(),lambda:None)
            self.assertEqual(u.metadata(addon/(NAME+'.toc'))['version'],'0.1.0')
    def test_game_open(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'AddOns'; addon=root/NAME; addon.mkdir(parents=True); (addon/(NAME+'.toc')).write_text(toc())
            def running(): raise RuntimeError('running')
            with self.assertRaises(RuntimeError): u.install_one(root,addon,REPO,'0.1.1',archive(),running)
            self.assertEqual(u.metadata(addon/(NAME+'.toc'))['version'],'0.1.0')
    def test_download_validation(self):
        import hashlib
        data=archive(); release={'tag_name':'v0.1.1','draft':False,'prerelease':False,'assets':[{'name':NAME+'.zip','state':'uploaded','size':len(data),'browser_download_url':'https://github.com/example/ebonupdater/releases/download/v0.1.1/EbonUpdater.zip','digest':'sha256:'+hashlib.sha256(data).hexdigest()}]}
        with patch.object(u,'get',side_effect=[json.dumps(release).encode(),data]):
            self.assertEqual(u.download(REPO,NAME,'0.1.1'),data)
        release['assets'][0]['digest']='sha256:'+'0'*64
        with patch.object(u,'get',side_effect=[json.dumps(release).encode(),data]):
            with self.assertRaises(ValueError): u.download(REPO,NAME,'0.1.1')

if __name__=='__main__': unittest.main()
