"""Privacy/closed-schema regressions. Synthetic tasks only, no native run."""
import asyncio
import copy
import json
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import passive
import run as runner

SECRET='SENTINEL_PRIVATE_CREDENTIAL_CAPABILITY_STORE_EXCEPTION_TASKNAME'


class Explosive:
    def __repr__(self): raise AssertionError(SECRET)
    def __str__(self): raise AssertionError(SECRET)


class PrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[4]/'test-private')
        self.addCleanup(self.temp.cleanup)
        self.journal=Path(self.temp.name)/'events.jsonl'
        self.observer=passive.Observer('fresh_sdk',self.journal)
        # Isolated module preimages, not installed Core monkeypatches or a real native run.
        self.loader=types.ModuleType('homeassistant.loader'); self.loader.__file__='synthetic-loader.py'
        exec(compile('class Integration:\n    async def async_get_platforms(self, platforms_that_exist):\n        return await self.future\n','synthetic-loader.py','exec'),self.loader.__dict__)
        self.module=types.ModuleType('homeassistant.helpers.integration_platform');self.module.__file__='synthetic-platform.py'
        exec(compile('async def _async_process_integration_platforms_for_component(integration, platforms_that_exist):\n    secret_local = "'+SECRET+'"\n    poisoned_local = integration.poison\n    await integration.async_get_platforms(platforms_that_exist)\n','synthetic-platform.py','exec'),self.module.__dict__)
        self.integration=self.loader.Integration()
        self.integration.domain='switch';self.integration.future=asyncio.get_running_loop().create_future();self.integration.poison=Explosive()
        self.patcher=patch.dict(sys.modules,{'homeassistant.loader':self.loader,'homeassistant.helpers.integration_platform':self.module})
        self.patcher.start();self.addCleanup(self.patcher.stop)

    async def task(self,platforms=None):
        task=asyncio.create_task(self.module._async_process_integration_platforms_for_component(self.integration,['trigger'] if platforms is None else platforms),name=SECRET)
        await asyncio.sleep(0) # unit test scheduling only; never in the diagnostic/native runner
        self.addAsyncCleanup(self.cleanup_task,task)
        return task

    async def cleanup_task(self,task):
        if not task.done(): task.cancel()
        try: await task
        except BaseException: pass

    def record(self,task):
        return logging.LogRecord('homeassistant.core',logging.WARNING,'private/'+SECRET,1222,passive.MESSAGE,(task,),(RuntimeError,RuntimeError(SECRET),None))

    def rows(self):
        raw=self.journal.read_text()
        self.assertNotIn(SECRET,raw)
        rows=[json.loads(line) for line in raw.splitlines()]
        for row in rows: passive.validate_event(row)
        return rows

    async def test_exact_code_ignores_secret_locals_exception_name_and_record_paths(self):
        task=await self.task()
        self.observer.emit(self.record(task))
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        await asyncio.sleep(0)
        self.observer.finish()
        rows=self.rows()
        self.assertEqual([r['event'] for r in rows],['start','warning','completion','summary'])
        self.assertEqual(rows[1]['integration'],{'domain':'switch','platforms':['trigger']})
        self.assertEqual(rows[1]['awaited'][0]['qualname'],'Integration.async_get_platforms')
        self.assertTrue(rows[2]['cancelled'])
        self.assertTrue(runner.consistent(rows,1))

    async def test_result_and_exception_are_never_retrieved_by_callback(self):
        task=await self.task(); self.observer.emit(self.record(task))
        self.integration.future.set_exception(RuntimeError(SECRET))
        try: await task
        except RuntimeError: pass # test owns retrieval; observer does not
        await asyncio.sleep(0);self.observer.finish()
        rows=self.rows()
        self.assertEqual(rows[2]['category'],'done_result_not_inspected')

    async def test_public_core_domain_outside_original_three_is_observed(self):
        self.integration.domain='light'
        task=await self.task(); self.observer.emit(self.record(task))
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        await asyncio.sleep(0); self.observer.finish()
        rows=self.rows()
        self.assertEqual(rows[1]['event'],'warning')
        self.assertEqual(rows[1]['integration']['domain'],'light')
        self.assertTrue(runner.consistent(rows,1))

    async def test_installed_catalog_version_mismatch_fails_closed(self):
        class WrongVersion:
            version='2026.10.3'
            def locate_file(self, path):
                raise AssertionError('must refuse before filesystem lookup')
        with patch.object(runner.importlib.metadata,'distribution',return_value=WrongVersion()):
            with self.assertRaises(ValueError):
                runner.validate_installed_catalog()

    async def test_catalog_all_members_share_output_validator_and_unknown_stays_private(self):
        task=await self.task()
        fields=passive.snapshot(task)
        row={'schema':1,'actor':'fresh_sdk','event':'warning','warning_id':1,**fields}
        pins=json.loads((runner.HERE/'source_pins.json').read_bytes())
        catalog=pins['public_core_catalog']['catalog']
        self.assertEqual(passive.DOMAINS,tuple(catalog['domains'])+('uninus_nutriculture',))
        for domain in passive.DOMAINS:
            row['integration']['domain']=domain
            passive.validate_event(row)
        for domain in (SECRET,'private_custom_component',Explosive()):
            self.integration.domain=domain
            with self.assertRaisesRegex(passive.Refusal,'^unknown_domain$'):
                passive.snapshot(task)
            row['integration']['domain']=domain
            with self.assertRaises(ValueError): passive.validate_event(row)
        self.integration.domain='private_custom_component'
        self.observer.emit(self.record(task));self.observer.finish()
        raw=self.journal.read_text()
        self.assertNotIn('private_custom_component',raw)
        self.assertEqual(self.rows()[1]['reason'],'unknown_domain')

    async def test_catalog_digest_version_shape_and_tamper_fail_closed(self):
        pins=json.loads((runner.HERE/'source_pins.json').read_bytes())
        path=Path(self.temp.name)/'catalog.json'
        cases=[]
        for key,value in [('version','2026.10.3'),('domains',['switch',SECRET]),('custom_domain',SECRET)]:
            changed=copy.deepcopy(pins)
            changed['public_core_catalog']['catalog'][key]=value
            # Even a recomputed embedded digest cannot expand the reviewed catalog.
            changed['public_core_catalog']['sha256']=runner.digest(runner.canonical(changed['public_core_catalog']['catalog']))
            cases.append(changed)
        changed=copy.deepcopy(pins);changed['public_core_catalog']['sha256']='0'*64;cases.append(changed)
        changed=copy.deepcopy(pins);changed['public_core_catalog']['extra']=SECRET;cases.append(changed)
        for changed in cases:
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): passive.load_domains(path)
        path.write_text('{')
        with self.assertRaises(ValueError): passive.load_domains(path)
        path.write_bytes(b' ' * 131073)
        with self.assertRaises(ValueError): passive.load_domains(path)

    async def test_actual_installed_catalog_metadata_only_no_component_imports(self):
        before={name for name in sys.modules if name=='homeassistant' or name.startswith('homeassistant.')}
        self.assertEqual(runner.validate_installed_catalog(),'2026.10.4')
        after={name for name in sys.modules if name=='homeassistant' or name.startswith('homeassistant.')}
        self.assertEqual(before,after)

    async def test_installed_catalog_missing_or_changed_manifest_fails_closed(self):
        root=Path(self.temp.name)/'components';root.mkdir()
        component=root/'switch';component.mkdir()
        manifest=component/'manifest.json'
        class Installed:
            version='2026.10.4'
            def locate_file(self,path):
                if path != 'homeassistant/components': raise AssertionError('unexpected lookup')
                return root
        with patch.object(runner.importlib.metadata,'distribution',return_value=Installed()):
            # No manifest, malformed domain, valid name but incomplete/changed catalog.
            with self.assertRaises(ValueError): runner.validate_installed_catalog()
            manifest.write_text(json.dumps({'domain':SECRET}))
            with self.assertRaises(ValueError): runner.validate_installed_catalog()
            manifest.write_text(json.dumps({'domain':'switch'}))
            with self.assertRaises(ValueError): runner.validate_installed_catalog()

    async def catalog_report(self):
        # Synthetic schema-only fixture, never written as native diagnostic evidence.
        task=await self.task()
        zero='0'*64
        warning={'schema':1,'actor':'fresh_sdk','event':'warning','warning_id':1,**passive.snapshot(task)}
        events={'producer':[{'schema':1,'actor':'producer','event':'start'},
            {'schema':1,'actor':'producer','event':'summary','observed':0,'rejected':0,'overflow':False,'write_failed':False}],
            'fresh_sdk':[{'schema':1,'actor':'fresh_sdk','event':'start'},warning,
            {'schema':1,'actor':'fresh_sdk','event':'completion','warning_id':1,'done':True,'cancelled':True,'cancelling':1,'category':'cancelled'},
            {'schema':1,'actor':'fresh_sdk','event':'summary','observed':1,'rejected':0,'overflow':False,'write_failed':False}]}
        return {'schema':1,'status':'OBSERVED','native_exit':0,
            'native_children':{'producer':0,'browser':0,'fresh_sdk':0},
            'native_export_warning_count':1,'warning_counts':{'producer':0,'fresh_sdk':1},
            'observer_counts':{'producer':0,'fresh_sdk':1},'observer_consistent':True,'events':events,
            'source_binding':{'backend_pin':runner.BASE,'card_pin':runner.CARD,'before_map_sha256':zero,'after_map_sha256':zero,'source_files':1,'source_unchanged':True,'imports':{}},
            'runtime':{'python':'3.14.5','core':'2026.10.4','playwright':'1.56.0','node':'v22.0.0','browser':None,'executables':{k:zero for k in runner.EXECUTABLES}},
            'module_bindings':{'homeassistant/'+p:zero for p in runner.CORE_FILES},
            'diagnostic_bindings':{p:zero for p in ('passive.py','run.py','test_passive.py','README.md','source_pins.json')},'limitations':runner.LIMITATIONS}

    async def test_report_core_version_matches_catalog(self):
        report=await self.catalog_report()
        runner.validate_report(report)
        report['runtime']['core']='2026.10.3'
        with self.assertRaises(ValueError): runner.validate_report(report)

    async def test_report_exact_catalog_membership(self):
        report=await self.catalog_report()
        for domain in passive.DOMAINS:
            report['events']['fresh_sdk'][1]['integration']['domain']=domain
            runner.validate_report(report)
        for domain in (SECRET,'private_custom_component',Explosive()):
            report['events']['fresh_sdk'][1]['integration']['domain']=domain
            with self.assertRaises(ValueError): runner.validate_report(report)

    async def test_unknown_domain_fails_closed(self):
        self.integration.domain=SECRET
        task=await self.task();self.observer.emit(self.record(task));self.observer.finish()
        rows=self.rows();self.assertEqual(rows[1]['reason'],'unknown_domain');self.assertFalse(runner.consistent(rows,1))

    async def test_unknown_platform_fails_closed(self):
        task=await self.task([SECRET]);self.observer.emit(self.record(task));self.observer.finish()
        self.assertEqual(self.rows()[1]['reason'],'unknown_platforms')

    async def test_lookalike_task_and_repr_are_not_trusted(self):
        self.observer.emit(self.record(Explosive()));self.observer.finish()
        self.assertEqual(self.rows()[1]['reason'],'unknown_task')

    async def test_unknown_coroutine_name_not_exported(self):
        async def unknown(): await asyncio.get_running_loop().create_future()
        unknown.__qualname__=SECRET
        task=asyncio.create_task(unknown(),name=SECRET);self.addAsyncCleanup(self.cleanup_task,task)
        await asyncio.sleep(0);self.observer.emit(self.record(task));self.observer.finish()
        self.assertEqual(self.rows()[1]['reason'],'unknown_coroutine')

    async def test_malformed_record_rejected_without_formatting(self):
        record=self.record(Explosive());record.args=(Explosive(),Explosive())
        self.observer.emit(record);self.observer.finish()
        self.assertEqual(self.rows()[1]['reason'],'invalid_record')

    async def test_nonmatching_warning_not_formatted_or_counted(self):
        record=self.record(Explosive());record.msg=Explosive()
        self.observer.emit(record);self.observer.finish()
        self.assertEqual(self.rows()[-1]['observed'],0)

    async def test_event_schema_rejects_secret_fields_and_bad_types(self):
        row={'schema':1,'actor':'producer','event':'start'}
        for bad in ({**row,'locals':SECRET},{**row,'schema':True},{**row,'actor':SECRET},{**row,'event':'future_schema'}):
            with self.assertRaises(ValueError): passive.validate_event(bad)
        with self.assertRaises(ValueError): passive.validate_event({'schema':1,'actor':'fresh_sdk','event':'completion','warning_id':1,'done':True,'cancelled':'false','cancelling':0,'category':'done_result_not_inspected'})

    async def test_overflow_is_bounded_and_not_success(self):
        for _ in range(200): self.observer.emit(self.record(Explosive()))
        self.observer.finish();rows=self.rows()
        self.assertLessEqual(len(rows),passive.MAX_EVENTS)
        self.assertTrue(rows[-1]['overflow']);self.assertEqual(rows[-1]['observed'],200)
        self.assertFalse(runner.consistent(rows,200))
        self.assertLessEqual(self.journal.stat().st_size,passive.MAX_JOURNAL_BYTES)

    async def test_counter_miss_is_not_success(self):
        self.observer.finish();self.assertFalse(runner.consistent(self.rows(),1))

    async def test_full_report_mutations_fail_closed(self):
        # Explicit synthetic schema fixture, never emitted as diagnostic evidence.
        zero='0'*64
        events={actor:[{'schema':1,'actor':actor,'event':'start'},
            {'schema':1,'actor':actor,'event':'summary','observed':0,'rejected':0,'overflow':False,'write_failed':False}]
            for actor in ('producer','fresh_sdk')}
        report={'schema':1,'status':'INCONCLUSIVE_NO_WARNING_OBSERVED','native_exit':0,
            'native_children':{'producer':0,'browser':0,'fresh_sdk':0},
            'native_export_warning_count':0,'warning_counts':{'producer':0,'fresh_sdk':0},
            'observer_counts':{'producer':0,'fresh_sdk':0},'observer_consistent':True,'events':events,
            'source_binding':{'backend_pin':runner.BASE,'card_pin':runner.CARD,'before_map_sha256':zero,'after_map_sha256':zero,'source_files':1,'source_unchanged':True,'imports':{}},
            'runtime':{'python':'3.14.5','core':'2026.10.4','playwright':'1.56.0','node':'v22.0.0','browser':None,'executables':{k:zero for k in runner.EXECUTABLES}},
            'module_bindings':{'homeassistant/'+p:zero for p in runner.CORE_FILES},
            'diagnostic_bindings':{p:zero for p in ('passive.py','run.py','test_passive.py','README.md','source_pins.json')},'limitations':runner.LIMITATIONS}
        runner.validate_report(report)
        mutations=[]
        row=copy.deepcopy(report);row['native_exit']=True;mutations.append(row)
        row=copy.deepcopy(report);row['status']='OBSERVED';mutations.append(row)
        row=copy.deepcopy(report);row['events']['producer']=[];mutations.append(row)
        row=copy.deepcopy(report);row['observer_counts']['producer']=1;mutations.append(row)
        row=copy.deepcopy(report);row['events']['fresh_sdk'][-1]['observed']=1;mutations.append(row)
        row=copy.deepcopy(report);row['runtime']['node']=SECRET;mutations.append(row)
        row=copy.deepcopy(report);row['private']=SECRET;mutations.append(row)
        row=copy.deepcopy(report);row['source_binding']['imports']['uninus-nutriculture/.storage/auth.json']=zero;mutations.append(row)
        for row in mutations:
            with self.assertRaises(ValueError): runner.validate_report(row)

    async def test_journal_unknown_schema_is_not_sanitized_into_success(self):
        self.journal.write_text(json.dumps({'schema':999,'actor':'fresh_sdk','event':'start','secret':SECRET})+'\n'+json.dumps({'schema':1,'actor':'fresh_sdk','event':'summary','observed':0,'rejected':0,'overflow':False,'write_failed':False})+'\n')
        self.journal.rename(Path(self.temp.name)/'fresh_sdk.jsonl')
        with self.assertRaises(ValueError): runner.read_events(Path(self.temp.name),'fresh_sdk')

    async def test_report_unknown_fields_schema_and_source_path_rejected(self):
        with self.assertRaises(ValueError): runner.validate_report({'schema':1,'secret':SECRET})
        for path in ('/private/'+SECRET,'uninus-nutriculture/tests/../../'+SECRET+'.py','uninus-nutriculture/.storage/auth.json','uninus-nutriculture/tests/'+SECRET+'\\x.py'):
            with self.assertRaises(ValueError): runner.source_path(path)


if __name__=='__main__':
    (Path(__file__).resolve().parents[4]/'test-private').mkdir(exist_ok=True)
    unittest.main()
