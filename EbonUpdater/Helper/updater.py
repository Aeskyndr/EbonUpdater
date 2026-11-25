"""EbonUpdater 0.1.1: opt-in Windows addon release installer."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import urllib.parse
import zipfile
from datetime import datetime, timezone

MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXPANDED = 300 * 1024 * 1024
MAX_FILES = 12000
NAME = re.compile(r'[A-Za-z0-9_-]{1,80}\Z')
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+\Z')
VERSION = re.compile(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\Z')


def version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError('Invalid stable version: ' + str(value))
    return tuple(map(int, value.split('.')))


def repository(value):
    if not isinstance(value, str) or not REPO.fullmatch(value):
        raise ValueError('Invalid GitHub repository')
    owner, repo = value.split('/')
    if owner.lower() == 'owner' or repo in ('.', '..'):
        raise ValueError('Set the real GitHub owner/repository in the TOC')
    return value.lower()


def parse_manifest(data):
    date, message = data['date'], data['message']
    if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError('Invalid manifest date')
    if not isinstance(message, str) or len(message) > 16384 or not message.startswith('EBONUPDATER1;'):
        raise ValueError('Not an EbonUpdater manifest')
    entries = {}
    for item in message.split(';')[1:]:
        name, pair = item.split('=')
        repo, v = pair.split(',')
        if not NAME.fullmatch(name) or name.lower() in entries:
            raise ValueError('Invalid or duplicate addon name')
        version(v)
        entries[name.lower()] = (repository(repo), v)
    return entries


def metadata(toc):
    result = {}
    for line in toc.read_text(encoding='utf-8-sig').splitlines():
        m = re.match(r'^##\s*([^:]+):\s*(.*?)\s*$', line)
        if m:
            key = m[1].strip().lower()
            if key in ('version', 'x-github') and key in result:
                raise ValueError('Duplicate TOC metadata: ' + key)
            result[key] = m[2]
    return result


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def discover(root):
    found = {}
    for p in root.iterdir():
        if not NAME.fullmatch(p.name) or not p.is_dir() or linked(p):
            continue
        toc = p / (p.name + '.toc')
        if not toc.is_file() or linked(toc):
            continue
        try:
            m = metadata(toc)
            if 'x-github' not in m:
                continue
            repo, v = repository(m['x-github']), m['version']
            version(v)
            found[p.name.lower()] = (p, repo, v)
        except (OSError, ValueError, KeyError, UnicodeError) as exc:
            print(f'Skipping {p.name}: {exc}')
    return found


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != 'https' or not u.hostname or not (u.hostname == 'github.com' or u.hostname.endswith('.github.com') or u.hostname.endswith('.githubusercontent.com')):
            raise ValueError('Unexpected download redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get(url, cap, api=False):
    request = urllib.request.Request(url, headers={'User-Agent':'EbonUpdater/0.1.1', 'Accept':'application/vnd.github+json' if api else '*/*'})
    with urllib.request.build_opener(HTTPSOnly()).open(request, timeout=30) as response:
        data = response.read(cap+1)
    if len(data) > cap:
        raise ValueError('Response exceeds size limit')
    return data


def download(repo, name, v):
    tag = 'v' + v
    release = json.loads(get(f'https://api.github.com/repos/{repo}/releases/tags/{tag}', 2*1024*1024, True))
    if release.get('tag_name') != tag or release.get('draft') or release.get('prerelease'):
        raise ValueError('No matching stable release')
    matches = [a for a in release['assets'] if a['name'] == name + '.zip' and a.get('state') == 'uploaded']
    if len(matches) != 1:
        raise ValueError('Expected exactly one uploaded asset ' + name + '.zip')
    asset = matches[0]
    expected = f'https://github.com/{repo}/releases/download/{tag}/{name}.zip'
    # GitHub may preserve owner/repository capitalization in its URLs.
    url = asset['browser_download_url']
    if url.lower() != expected.lower() or not 0 < asset['size'] <= MAX_DOWNLOAD:
        raise ValueError('Unexpected asset URL or size')
    data = get(url, MAX_DOWNLOAD)
    if len(data) != asset['size']:
        raise ValueError('Downloaded size mismatch')
    digest = asset.get('digest')
    if digest and digest.lower() != 'sha256:' + hashlib.sha256(data).hexdigest():
        raise ValueError('Release digest mismatch')
    if not digest:
        print('  Note: GitHub supplied no asset digest; using HTTPS and package validation.')
    return data


def safe_parts(name):
    if '\\' in name or name.startswith('/') or '\x00' in name:
        raise ValueError('Unsafe ZIP path')
    parts = name.rstrip('/').split('/')
    for part in parts:
        if not part or part in ('.','..') or part.endswith((' ','.')) or any(ord(c)<32 or c in '<>:"|?*' for c in part):
            raise ValueError('Unsafe ZIP path')
        if re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])',part.split('.')[0]):
            raise ValueError('Reserved Windows filename')
    return parts


def extract(data, stage, name, repo, v):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        if not infos or len(infos)>MAX_FILES or sum(x.file_size for x in infos)>MAX_EXPANDED:
            raise ValueError('ZIP exceeds limits or is empty')
        seen = {}
        for item in infos:
            parts = safe_parts(item.orig_filename)
            if parts[0] != name or (len(parts)==1 and not item.is_dir()):
                raise ValueError('ZIP must contain only the exact addon folder: '+name)
            kind = stat.S_IFMT(item.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or item.external_attr & 0x400:
                raise ValueError('ZIP links or special files are not permitted')
            # Do not allow Windows case collisions, including parent directory aliases.
            for n in range(1,len(parts)+1):
                key = '/'.join(parts[:n]).casefold()
                exact = '/'.join(parts[:n])
                if key in seen and seen[key] != exact:
                    raise ValueError('ZIP case collision')
                seen[key] = exact
            target = stage.joinpath(*parts)
            if item.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(item) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src,dst)
    path = stage/name
    m = metadata(path/(name+'.toc'))
    if repository(m['x-github']) != repo or m['version'] != v:
        raise ValueError('Downloaded TOC repository/version does not match release')
    return path


def ensure_closed(game):
    if os.name != 'nt':
        raise RuntimeError('Installation is Windows-only; close WoW before using the helper.')
    # Conservative: block WoW/Ebonhold named processes and any executable under the game root.
    script = '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath,ProcessId | ConvertTo-Json -Compress'
    run = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=30,check=True)
    processes=json.loads(run.stdout.decode('utf-8-sig',errors='replace'))
    if isinstance(processes,dict): processes=[processes]
    if not isinstance(processes,list) or not processes:
        raise RuntimeError('Could not verify game is closed')
    for p in processes:
        name=(p.get('Name') or '').lower()
        exe=p.get('ExecutablePath')
        if p.get('ProcessId') == os.getpid(): continue
        # PyInstaller one-file mode uses a parent bootloader of the same executable.
        import sys
        if getattr(sys, 'frozen', False) and p.get('ProcessId') == os.getppid() and exe and Path(exe).resolve() == Path(sys.executable).resolve():
            continue
        if re.match(r'^(wow|ebonhold)',name):
            raise RuntimeError('Close WoW/Ebonhold and its launcher before installing: '+name)
        if exe:
            try: Path(exe).resolve().relative_to(game.resolve())
            except ValueError: continue
            raise RuntimeError('Close processes running in the game folder: '+name)


def install_one(root, addon, repo, v, data, closed):
    # Stage and back up outside AddOns but on the same volume for atomic directory renames.
    work=root.parent/'EbonUpdater-backups'
    work.mkdir(exist_ok=True)
    if linked(work): raise ValueError('Backup directory is a link')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=work/(addon.name+'-'+stamp)
    with tempfile.TemporaryDirectory(prefix='.stage-',dir=work) as tmp:
        new=extract(data,Path(tmp),addon.name,repo,v)
        closed()
        if linked(addon) or linked(addon/(addon.name+'.toc')): raise ValueError('Addon directory or TOC became a link')
        current=metadata(addon/(addon.name+'.toc'))
        if repository(current['x-github'])!=repo or version(current['version'])>=version(v):
            raise ValueError('Installed addon changed since check; run again')
        addon.rename(backup)
        try:
            new.rename(addon)
        except BaseException:
            try: backup.rename(addon)
            except OSError as e: raise RuntimeError(f'Rollback failed; restore manually from {backup}') from e
            raise
    return backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game',nargs='?',help='Game root containing Interface/AddOns')
    parser.add_argument('--check',action='store_true',help='Check only, never install')
    args=parser.parse_args()
    value=args.game or input('Ebonhold game folder (where Wow.exe is): ').strip().strip('"')
    if not value: raise ValueError('No game folder supplied')
    game=Path(value).expanduser().resolve()
    root=game/'Interface'/'AddOns'
    if not root.is_dir() or linked(root) or linked(root.parent): raise ValueError('Invalid Interface/AddOns directory')
    found=discover(root)
    if 'ebonupdater' not in found: raise ValueError('Install and configure EbonUpdater.toc first')
    _, repo, _=found['ebonupdater']
    remote=parse_manifest(json.loads(get(f'https://raw.githubusercontent.com/{repo}/main/versions.json',65536)))
    if remote.get('ebonupdater',('',))[0]!=repo: raise ValueError('Manifest repository mismatch')
    updates=[]
    for key,(path,r,v) in sorted(found.items()):
        entry=remote.get(key)
        if not entry or entry[0]!=r:
            print(f'{path.name}: {v} (not tracked / repository mismatch)'); continue
        latest=entry[1]
        print(f'{path.name}: {v} -> {latest}' + (' [UPDATE]' if version(latest)>version(v) else ''))
        if version(latest)>version(v): updates.append((path,r,latest))
    if not updates or args.check: return
    print(f'\n{len(updates)} update(s). Backups are kept in Interface/EbonUpdater-backups.')
    if input('Close WoW, then type UPDATE to install all: ').strip()!='UPDATE': return
    ensure_closed(game)
    failures=0
    for path,r,v in updates:
        try:
            print(f'Downloading {path.name} {v}...')
            data=download(r,path.name,v)
            backup=install_one(root,path,r,v,data,lambda:ensure_closed(game))
            print('Installed; backup:',backup)
        except Exception as exc:
            failures+=1; print(f'FAILED {path.name}: {exc}')
    if failures: raise RuntimeError(f'{failures} update(s) failed; see messages above.')


if __name__=='__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as exc:
        print('EbonUpdater stopped:',exc)
        raise SystemExit(1)
