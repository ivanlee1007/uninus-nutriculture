"""Closed-schema passive logger. Never formats a LogRecord or retrieves a result."""
import atexit
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import types

SCHEMA = 1
MAX_WARNINGS = 64
MAX_EVENTS = 132
MAX_EVENT_BYTES = 4096
MAX_JOURNAL_BYTES = MAX_EVENTS * MAX_EVENT_BYTES
PHRASE = 'was still running after final writes shutdown stage'
MESSAGE = ('Task %s was still running after final writes shutdown stage; '
           'Integrations should cancel non-critical tasks when receiving '
           'the stop event to prevent delaying shutdown')
CATALOG_SHA256 = '25b89ec9a1b5bfd7fff8009eb635c6b29b13e01044f24cc91534b9375457508b'


def load_domains(path):
    # Static reviewed public source data, never runtime/config-discovered acceptance.
    if path.stat().st_size > 131072: raise ValueError('catalog')
    row = json.loads(path.read_bytes())['public_core_catalog']
    if type(row) is not dict or set(row) != {'catalog','sha256'}:
        raise ValueError('catalog')
    catalog = row['catalog']
    if type(catalog) is not dict or set(catalog) != {'distribution','version','derivation','domains','manifest_map_sha256','custom_domain','custom_backend_pin','custom_manifest_sha256'}:
        raise ValueError('catalog')
    if row['sha256'] != CATALOG_SHA256 or hashlib.sha256(json.dumps(catalog,sort_keys=True,separators=(',',':')).encode()).hexdigest() != CATALOG_SHA256:
        raise ValueError('catalog')
    if catalog['distribution'] != 'homeassistant' or catalog['version'] != '2026.10.4' or catalog['custom_domain'] != 'uninus_nutriculture':
        raise ValueError('catalog')
    domains = catalog['domains']
    if type(domains) is not list or not 1 <= len(domains) <= 4096 or any(type(x) is not str or not 1 <= len(x) <= 64 for x in domains):
        raise ValueError('catalog')
    if domains != sorted(set(domains)) or catalog['custom_domain'] in domains:
        raise ValueError('catalog')
    return tuple(domains) + (catalog['custom_domain'],)


DOMAINS = load_domains(Path(__file__).with_name('source_pins.json'))
PLATFORMS = ('condition', 'trigger')
# Unknown identities fail closed; add no regex or string-coercion fallback.
IDENTITIES = {
    'platform_component': ('homeassistant.helpers.integration_platform',
        '_async_process_integration_platforms_for_component',
        'homeassistant/helpers/integration_platform.py'),
    'platform_initial': ('homeassistant.helpers.integration_platform',
        '_async_process_integration_platforms',
        'homeassistant/helpers/integration_platform.py'),
    'get_platforms': ('homeassistant.loader', 'Integration.async_get_platforms',
        'homeassistant/loader.py'),
}
REASONS = ('unknown_task', 'unknown_coroutine', 'unknown_awaitable',
           'unknown_integration', 'unknown_domain', 'unknown_platforms',
           'invalid_record', 'observer_error', 'overflow')


def exact(row, keys):
    if type(row) is not dict or set(row) != set(keys):
        raise ValueError('schema')


def integer(value, low=0, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('schema')


def boolean(value):
    if type(value) is not bool:
        raise ValueError('schema')


def identity(row):
    exact(row, ('kind', 'module', 'qualname', 'source', 'line', 'definition_line'))
    if type(row['kind']) is not str or row['kind'] not in IDENTITIES:
        raise ValueError('schema')
    if (row['module'], row['qualname'], row['source']) != IDENTITIES[row['kind']]:
        raise ValueError('schema')
    integer(row['line'], 1, 10000)
    integer(row['definition_line'], 1, 10000)


def validate_event(row):
    if type(row) is not dict or row.get('schema') != SCHEMA or type(row.get('schema')) is not int:
        raise ValueError('schema')
    if row.get('actor') not in ('producer', 'fresh_sdk') or type(row.get('actor')) is not str:
        raise ValueError('schema')
    base = ('schema', 'actor', 'event')
    event = row.get('event')
    if event == 'start':
        exact(row, base)
    elif event == 'warning':
        exact(row, base + ('warning_id','task','awaited','await_terminal','integration','pending','done','cancelled','cancelling'))
        integer(row['warning_id'],1,MAX_WARNINGS)
        identity(row['task'])
        if type(row['awaited']) is not list or len(row['awaited']) > 8:
            raise ValueError('schema')
        for item in row['awaited']: identity(item)
        if row['await_terminal'] not in ('future_iterator','none'): raise ValueError('schema')
        exact(row['integration'], ('domain','platforms'))
        if type(row['integration']['domain']) is not str or row['integration']['domain'] not in DOMAINS: raise ValueError('schema')
        platforms = row['integration']['platforms']
        if type(platforms) is not list or not 1 <= len(platforms) <= 2 or any(type(p) is not str or p not in PLATFORMS for p in platforms) or len(set(platforms)) != len(platforms): raise ValueError('schema')
        for key in ('pending','done','cancelled'): boolean(row[key])
        if row['pending'] != (not row['done']): raise ValueError('schema')
        integer(row['cancelling'],0,100)
    elif event == 'completion':
        exact(row, base + ('warning_id','done','cancelled','cancelling','category'))
        integer(row['warning_id'],1,MAX_WARNINGS)
        boolean(row['done']); boolean(row['cancelled']); integer(row['cancelling'],0,100)
        if not row['done'] or row['category'] != ('cancelled' if row['cancelled'] else 'done_result_not_inspected'): raise ValueError('schema')
    elif event == 'rejected':
        exact(row, base + ('warning_id','reason'))
        integer(row['warning_id'],1,100000)
        if type(row['reason']) is not str or row['reason'] not in REASONS: raise ValueError('schema')
    elif event == 'summary':
        exact(row, base + ('observed','rejected','overflow','write_failed'))
        integer(row['observed']); integer(row['rejected']); boolean(row['overflow']); boolean(row['write_failed'])
    else:
        raise ValueError('schema')
    if len(json.dumps(row,sort_keys=True).encode()) > MAX_EVENT_BYTES - 1:
        raise ValueError('schema')
    return row


class Refusal(Exception):
    pass


def coroutine_identity(coro):
    if type(coro) is not types.CoroutineType or coro.cr_frame is None:
        raise Refusal('unknown_coroutine')
    code = coro.cr_code
    for key,(module_name,qualname,source) in IDENTITIES.items():
        module = sys.modules.get(module_name)
        obj = module
        for part in qualname.split('.'):
            obj = vars(obj).get(part) if obj is not None else None
        if type(obj) is types.FunctionType and obj.__code__ is code:
            # Only the exact installed Core function, not a lookalike qualname.
            if coro.cr_frame.f_globals is not vars(module):
                raise Refusal('unknown_coroutine')
            if Path(code.co_filename).resolve() != Path(module.__file__).resolve():
                raise Refusal('unknown_coroutine')
            return {'kind':key,'module':module_name,'qualname':qualname,'source':source,
                    'line':coro.cr_frame.f_lineno,'definition_line':code.co_firstlineno}
    raise Refusal('unknown_coroutine')


def snapshot(task):
    if type(task) is not asyncio.Task:
        raise Refusal('unknown_task')
    coro = task.get_coro()
    task_identity = coroutine_identity(coro)
    if task_identity['kind'] != 'platform_component':
        raise Refusal('unknown_coroutine')
    # No general locals serialization: these two named values only, on exact code.
    frame = coro.cr_frame
    integration = frame.f_locals.get('integration')
    loader = sys.modules.get('homeassistant.loader')
    cls = vars(loader).get('Integration') if loader is not None else None
    if type(integration) is not cls:
        raise Refusal('unknown_integration')
    data = object.__getattribute__(integration, '__dict__')
    domain = data.get('domain')
    if domain is None:
        manifest = data.get('manifest')
        domain = manifest.get('domain') if type(manifest) is dict else None
    if type(domain) is not str or domain not in DOMAINS:
        raise Refusal('unknown_domain')
    platforms = frame.f_locals.get('platforms_that_exist')
    if type(platforms) is not list or not 1 <= len(platforms) <= 2 or any(type(p) is not str or p not in PLATFORMS for p in platforms) or len(set(platforms)) != len(platforms):
        raise Refusal('unknown_platforms')
    chain=[]
    awaited=coro.cr_await
    while type(awaited) is types.CoroutineType:
        if len(chain) >= 8: raise Refusal('unknown_awaitable')
        chain.append(coroutine_identity(awaited))
        awaited=awaited.cr_await
    terminal='none'
    if awaited is not None:
        waiter=task._fut_waiter
        if type(waiter) is not asyncio.Future or type(awaited) is not type(asyncio.Future.__await__(waiter)):
            raise Refusal('unknown_awaitable')
        terminal='future_iterator'
    return {'task':task_identity,'awaited':chain,'await_terminal':terminal,
            'integration':{'domain':domain,'platforms':list(platforms)},
            'pending':not task.done(),'done':task.done(),'cancelled':task.cancelled(),
            'cancelling':task.cancelling()}


class Observer(logging.Handler):
    def __init__(self, actor, journal):
        super().__init__(logging.WARNING)
        if actor not in ('producer','fresh_sdk'): raise ValueError('actor')
        self.actor=actor; self.journal=Path(journal)
        self.observed=0; self.rejected=0; self.count=0
        self.overflow=False; self.write_failed=False
        self.write('start')

    def write(self,event,**fields):
        try:
            row=validate_event({'schema':SCHEMA,'actor':self.actor,'event':event,**fields})
            if self.count >= MAX_EVENTS: self.overflow=True; return
            raw=(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
            if self.journal.exists() and self.journal.stat().st_size + len(raw) > MAX_JOURNAL_BYTES:
                self.overflow=True; return
            with self.journal.open('ab') as out: out.write(raw)
            self.count+=1
        except BaseException:
            # No traceback, exception message, arbitrary fields or logging recursion.
            self.write_failed=True

    def emit(self,record):
        # No getMessage(), repr(task), custom name, args formatting or exception access.
        if record.name != 'homeassistant.core' or type(record.msg) is not str or record.msg != MESSAGE:
            return
        self.observed+=1
        number=self.observed
        if number > MAX_WARNINGS:
            if not self.overflow:
                self.overflow=True; self.rejected+=1
                self.write('rejected',warning_id=number,reason='overflow')
            return
        try:
            if record.levelno != logging.WARNING or type(record.args) is not tuple or len(record.args)!=1:
                raise Refusal('invalid_record')
            task=record.args[0]
            fields=snapshot(task)
            self.write('warning',warning_id=number,**fields)
            # Observe completion only. Core remains the sole cancelling/waiting actor.
            def completed(done):
                cancelled=done.cancelled()
                self.write('completion',warning_id=number,done=done.done(),
                    cancelled=cancelled,cancelling=done.cancelling(),
                    category='cancelled' if cancelled else 'done_result_not_inspected')
            task.add_done_callback(completed)
        except Refusal as refusal:
            self.rejected+=1
            reason=refusal.args[0]
            self.write('rejected',warning_id=number,reason=reason if reason in REASONS else 'observer_error')
        except BaseException:
            self.rejected+=1
            self.write('rejected',warning_id=number,reason='observer_error')

    def finish(self):
        self.write('summary',observed=self.observed,rejected=self.rejected,
                   overflow=self.overflow,write_failed=self.write_failed)


def install():
    # Fixed native actors only; verifier/browser imports and inventory stay unchanged.
    if Path(sys.argv[0]).name != 'p5a_visual_native.py': return
    actor='fresh_sdk' if len(sys.argv)>1 and sys.argv[1]=='--readback' else 'producer'
    journal=Path(__file__).resolve().parent.parent / (actor+'.jsonl')
    observer=Observer(actor,journal)
    logging.getLogger('homeassistant.core').addHandler(observer)
    atexit.register(observer.finish)
