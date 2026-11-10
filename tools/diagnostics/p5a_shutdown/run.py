"""One bounded P5a control; private native logs, one closed sanitized report."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys

from passive import MAX_EVENTS, MAX_JOURNAL_BYTES, PHRASE, validate_event, exact, integer, boolean, load_domains

BASE='471f7e56e0ec9a28667fdec0c6e9dd76d7e751f4'
CARD='2112c09f3b756a5b69aa8566c26ec32039b18a06'
HERE=Path(__file__).resolve().parent
CORE_FILES=('core.py','loader.py','setup.py','bootstrap.py','helpers/integration_platform.py','helpers/condition.py','helpers/trigger/__init__.py')
EXECUTABLES=('python','base_python','node','chromium','playwright_node')
LIMITATIONS=['PASSIVE_OBSERVER_PERTURBS_TIMING','NOT_RETROSPECTIVE_HOSTED_ATTRIBUTION','NOT_ZERO_WARNING_ACCEPTANCE','NO_DEPLOYMENT_OR_PRODUCT_CHANGE','COMPLETION_RESULT_NOT_INSPECTED','UNKNOWN_IDENTITIES_FAIL_CLOSED']


def digest(data): return hashlib.sha256(data).hexdigest()
def sha(path): return digest(Path(path).read_bytes())
def canonical(data): return json.dumps(data,sort_keys=True,separators=(',',':')).encode()
def dump(path,data): Path(path).write_bytes(canonical(data)+b'\n')
def hash_value(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None: raise ValueError('schema')
def version(value):
    if type(value) is not str or re.fullmatch('v?[0-9]+(?:[.][0-9]+){1,3}',value) is None: raise ValueError('schema')
def source_path(value):
    if type(value) is not str or re.fullmatch(r'(uninus-nutriculture|uninus-nutriculture-card)/[A-Za-z0-9_./-]+',value) is None: raise ValueError('schema')
    p=PurePosixPath(value)
    if '..' in p.parts or any(x in {'.git','.storage','runtime','auth','private-ha'} for x in p.parts): raise ValueError('schema')
    if p.parts[1] not in ('custom_components','tests','tools') or p.suffix not in ('.py','.json','.yaml'): raise ValueError('schema')


def validate_installed_catalog():
    # Parent preflight only, before native launch. No component imports or user data.
    path=HERE/'source_pins.json'
    domains=load_domains(path)
    catalog=json.loads(path.read_bytes())['public_core_catalog']['catalog']
    distribution=importlib.metadata.distribution('homeassistant')
    if distribution.version != catalog['version']: raise ValueError('catalog')
    components=Path(distribution.locate_file('homeassistant/components'))
    manifests={}
    for count,entry in enumerate(components.iterdir(),1):
        if count > 4096: raise ValueError('catalog')
        if entry.name=='__pycache__': continue
        if entry.is_symlink(): raise ValueError('catalog')
        if not entry.is_dir(): continue
        manifest=entry/'manifest.json'
        if not manifest.is_file() or manifest.is_symlink() or manifest.stat().st_size>131072:
            raise ValueError('catalog')
        if json.loads(manifest.read_bytes()).get('domain') != entry.name:
            raise ValueError('catalog')
        manifests[entry.name]=sha(manifest)
    if tuple(sorted(manifests)) != domains[:-1] or digest(canonical(manifests)) != catalog['manifest_map_sha256']:
        raise ValueError('catalog')
    return catalog['version']


def inventory(pair):
    result={}
    for name in ('uninus-nutriculture','uninus-nutriculture-card'):
        root=pair/name
        for path in root.rglob('*'):
            if '.git' in path.relative_to(root).parts: continue
            if path.is_symlink(): raise ValueError('symlink')
            if path.is_file():
                result[path.relative_to(pair).as_posix()]={'sha256':sha(path),'mode':path.stat().st_mode & 0o777}
    return result


def read_events(private,actor):
    path=private/(actor+'.jsonl')
    if not path.is_file() or path.stat().st_size>MAX_JOURNAL_BYTES: raise ValueError('journal')
    lines=path.read_bytes().splitlines()
    if not 2 <= len(lines) <= MAX_EVENTS: raise ValueError('journal')
    rows=[validate_event(json.loads(line)) for line in lines]
    if any(row['actor'] != actor for row in rows): raise ValueError('journal')
    if rows[0]['event']!='start' or rows[-1]['event']!='summary': raise ValueError('journal')
    if any(r['event'] in ('start','summary') for r in rows[1:-1]): raise ValueError('journal')
    return rows


def consistent(rows,count):
    summary=rows[-1]
    warnings=[r for r in rows if r['event']=='warning']
    completions=[r for r in rows if r['event']=='completion']
    if any(r['event']=='rejected' for r in rows): return False
    ids=[r['warning_id'] for r in warnings]
    done=[r['warning_id'] for r in completions]
    return (summary['observed']==count==len(warnings) and summary['rejected']==0 and
            not summary['overflow'] and not summary['write_failed'] and
            ids==list(range(1,count+1)) and sorted(done)==ids)


def validate_report(report):
    exact(report,('schema','status','native_exit','native_children','native_export_warning_count','warning_counts','observer_counts','observer_consistent','events','source_binding','runtime','module_bindings','diagnostic_bindings','limitations'))
    if type(report['schema']) is not int or report['schema']!=1: raise ValueError('schema')
    if report['status'] not in ('OBSERVED','INCONCLUSIVE_NO_WARNING_OBSERVED','INVALID'): raise ValueError('schema')
    integer(report['native_exit'],-100000,100000)
    exact(report['native_children'],('producer','browser','fresh_sdk'))
    for value in report['native_children'].values():
        if value is not None: integer(value,-100000,100000)
    if report['native_export_warning_count'] is not None: integer(report['native_export_warning_count'])
    for key in ('warning_counts','observer_counts'):
        exact(report[key],('producer','fresh_sdk'))
        for value in report[key].values(): integer(value)
    boolean(report['observer_consistent'])
    exact(report['events'],('producer','fresh_sdk'))
    for actor,rows in report['events'].items():
        if type(rows) is not list or len(rows)>MAX_EVENTS: raise ValueError('schema')
        for row in rows:
            validate_event(row)
            if row['actor']!=actor: raise ValueError('schema')
    exact(report['source_binding'],('backend_pin','card_pin','before_map_sha256','after_map_sha256','source_files','source_unchanged','imports'))
    binding=report['source_binding']
    if binding['backend_pin']!=BASE or binding['card_pin']!=CARD: raise ValueError('schema')
    for key in ('before_map_sha256','after_map_sha256'): hash_value(binding[key])
    integer(binding['source_files'],1,20000); boolean(binding['source_unchanged'])
    if type(binding['imports']) is not dict or len(binding['imports'])>100: raise ValueError('schema')
    for path,value in binding['imports'].items(): source_path(path); hash_value(value)
    exact(report['runtime'],('python','core','playwright','node','browser','executables'))
    for key in ('python','core','playwright','node'): version(report['runtime'][key])
    if report['runtime']['core']!='2026.10.4': raise ValueError('schema')
    if report['runtime']['browser'] is not None: version(report['runtime']['browser'])
    exact(report['runtime']['executables'],EXECUTABLES)
    for value in report['runtime']['executables'].values(): hash_value(value)
    exact(report['module_bindings'],tuple('homeassistant/'+p for p in CORE_FILES))
    for value in report['module_bindings'].values(): hash_value(value)
    expected=('passive.py','run.py','test_passive.py','README.md','source_pins.json')
    exact(report['diagnostic_bindings'],expected)
    for value in report['diagnostic_bindings'].values(): hash_value(value)
    if report['limitations']!=LIMITATIONS: raise ValueError('schema')
    # Reject contradictory success, even if the primitive schema is valid.
    total=sum(report['warning_counts'].values())
    journals_ok=True
    for actor,rows in report['events'].items():
        starts=[r for r in rows if r['event']=='start']
        summaries=[r for r in rows if r['event']=='summary']
        complete_journal=(len(rows)>=2 and len(starts)==1 and len(summaries)==1 and
            rows[0]['event']=='start' and rows[-1]['event']=='summary')
        if complete_journal:
            if report['observer_counts'][actor]!=rows[-1]['observed']: raise ValueError('schema')
            journals_ok=journals_ok and consistent(rows,report['warning_counts'][actor])
        else:
            journals_ok=False
    if report['observer_consistent'] and not journals_ok: raise ValueError('schema')
    valid=(report['native_exit']==0 and all(v==0 for v in report['native_children'].values()) and
           binding['source_unchanged'] and report['observer_consistent'] and
           report['native_export_warning_count']==total and
           report['observer_counts']==report['warning_counts'])
    if report['status']!='INVALID' and not valid: raise ValueError('schema')
    if report['status']=='OBSERVED' and not total: raise ValueError('schema')
    if report['status']=='INCONCLUSIVE_NO_WARNING_OBSERVED' and total: raise ValueError('schema')
    if len(canonical(report))>131072: raise ValueError('schema')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    pair=args.pair.resolve(); private=args.private.resolve(); output=args.output.resolve()
    backend=pair/'uninus-nutriculture'; card=pair/'uninus-nutriculture-card'
    assert not private.is_relative_to(pair) and not output.is_relative_to(pair)
    assert not output.exists() and not private.exists()
    private.mkdir(parents=True,exist_ok=False)
    # This exclusive directory is the one-attempt marker. Never reuse it.
    pins=json.loads((HERE/'source_pins.json').read_bytes())
    assert pins['backend_pin']==BASE and pins['card_pin']==CARD
    for relative,expected in pins['files'].items(): assert sha(pair/relative)==expected
    validate_installed_catalog()
    before=inventory(pair); dump(private/'source-before.json',before)
    import homeassistant
    import playwright
    core=Path(homeassistant.__file__).parent
    driver=Path(playwright.__file__).parent/'driver'/('node.exe' if os.name=='nt' else 'node')
    executables={'python':Path(sys.executable),'base_python':Path(sys._base_executable),'node':Path(os.environ['NODE']),'chromium':Path(os.environ['CHROMIUM_EXECUTABLE']),'playwright_node':driver}
    assert all(p.is_file() for p in executables.values())
    runtime={'python':'.'.join(map(str,sys.version_info[:3])),
             'core':importlib.metadata.version('homeassistant'),
             'playwright':importlib.metadata.version('playwright'),
             'node':subprocess.check_output([str(executables['node']),'--version'],stderr=subprocess.DEVNULL,text=True).strip(),
             'browser':None,'executables':{k:sha(p) for k,p in executables.items()}}
    assert runtime['core']=='2026.10.4' and runtime['playwright']=='1.56.0'
    module_bindings={'homeassistant/'+p:sha(core/p) for p in CORE_FILES}
    hook=private/'hook';hook.mkdir()
    shutil.copyfile(HERE/'passive.py',hook/'passive.py')
    shutil.copyfile(HERE/'source_pins.json',hook/'source_pins.json')
    (hook/'sitecustomize.py').write_text("import passive\npassive.install()\n",encoding='utf8')
    dump(private/'hook-inputs.json',{p.name:sha(p) for p in hook.iterdir()})
    env=dict(os.environ)
    for key in ('P3C_CAPTURE_DIR','P3C_TERMINAL_ROOT','P4B_JOIN_OUTPUT','P5A_JOIN_OUTPUT','BROWSER_EVIDENCE_DIR','PYTHONPYCACHEPREFIX'):
        env.pop(key,None)
    env.update(PYTHONDONTWRITEBYTECODE='1',P5A_CARD_PYTHON=sys.executable,
        P5A_JOIN_OUTPUT=str(private/'native'),BROWSER_EVIDENCE_DIR=str(private/'browser'),
        PYTHONPATH=os.pathsep.join([str(hook),str(backend),str(backend/'tests'),*filter(None,os.environ.get('PYTHONPATH','').split(os.pathsep))]))
    cmd=[sys.executable,'-B',str(backend/'tools/p5a_visual_verify.py'),'--run-default']
    # Never forward native stdout/stderr, DTOs, traces or exception messages.
    with (private/'verifier.stdout.log').open('wb') as out,(private/'verifier.stderr.log').open('wb') as err:
        child=subprocess.Popen(cmd,cwd=backend,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
            start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        dump(private/'owned-launch.json',{'pid':child.pid,'bounded_seconds':480})
        try: code=child.wait(timeout=480)
        except subprocess.TimeoutExpired:
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
            else: os.killpg(child.pid,signal.SIGKILL)
            code=child.wait(timeout=20)
    after=inventory(pair);dump(private/'source-after.json',after)
    if module_bindings != {'homeassistant/'+p:sha(core/p) for p in CORE_FILES}:
        raise ValueError('runtime_source_changed')
    if runtime['executables'] != {k:sha(p) for k,p in executables.items()}:
        raise ValueError('runtime_executable_changed')
    native=private/'native'; attempt=native/'attempt1'
    def load(path): return json.loads(path.read_bytes())
    children={}
    for key,path,field in [('producer',native/'producer-exit.json','exit_code'),('browser',attempt/'result.json','browser_exit_code'),('fresh_sdk',attempt/'fresh-exit.json','exit_code')]:
        try: value=load(path)[field]; integer(value,-100000,100000); children[key]=value
        except (OSError,ValueError,KeyError): children[key]=None
    counts={}
    for actor,path in [('producer',native/'producer.log'),('fresh_sdk',attempt/'fresh.stderr.log')]:
        # Counts only; no bytes, lines, task repr or matching snippets are exported.
        counts[actor]=path.read_bytes().count(PHRASE.encode()) if path.is_file() else 0
    events={}; valid=True
    for actor in ('producer','fresh_sdk'):
        try: events[actor]=read_events(private,actor)
        except (OSError,ValueError,KeyError): events[actor]=[]; valid=False
    observed={actor:(rows[-1]['observed'] if rows else 0) for actor,rows in events.items()}
    valid=valid and all(consistent(events[actor],counts[actor]) for actor in events)
    native_export=None
    safe=native.parent/(native.name+'-safe-export')/'ci-verified.json'
    if safe.is_file():
        row=load(safe); native_export=row['shutdown_warning_count']; integer(native_export)
        browser=row['browser']; version(browser); runtime['browser']=browser
    imports={}
    if (attempt/'actual-imports.json').is_file():
        for module,row in load(attempt/'actual-imports.json').items():
            source=Path(row['path']).resolve()
            assert source.is_relative_to(backend)
            relative=source.relative_to(pair).as_posix();source_path(relative)
            hash_value(row['sha256']); assert sha(source)==row['sha256']
            imports[relative]=row['sha256']
    valid=valid and code==0 and all(v==0 for v in children.values()) and before==after and native_export==sum(counts.values())
    report={'schema':1,'status':('OBSERVED' if sum(counts.values()) else 'INCONCLUSIVE_NO_WARNING_OBSERVED') if valid else 'INVALID',
        'native_exit':code,'native_children':children,'native_export_warning_count':native_export,
        'warning_counts':counts,'observer_counts':observed,'observer_consistent':bool(valid),
        'events':events,'source_binding':{'backend_pin':BASE,'card_pin':CARD,
            'before_map_sha256':digest(canonical(before)),'after_map_sha256':digest(canonical(after)),
            'source_files':len(before),'source_unchanged':before==after,'imports':imports},
        'runtime':runtime,'module_bindings':module_bindings,
        'diagnostic_bindings':{name:sha(HERE/name) for name in ('passive.py','run.py','test_passive.py','README.md','source_pins.json')},
        'limitations':LIMITATIONS}
    validate_report(report)
    output.parent.mkdir(parents=True,exist_ok=True);dump(output,report)
    # Read back and revalidate the sole artifact; no other files may be uploaded.
    validate_report(load(output))
    print(json.dumps({'status':report['status'],'native_exit':code,'warning_count':sum(counts.values())}))
    return code if code!=0 else (0 if valid else 2)


if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        print('DIAGNOSTIC_FAILED_CLOSED',file=sys.stderr)
        sys.exit(2)
