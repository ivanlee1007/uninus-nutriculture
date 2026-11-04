"""Concrete repair round2: queued revocation, accepted bounds and reset truth."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'custom_components/uninus_nutriculture'
def edit(f,a,b,n=1):
 p=R/f;s=p.read_text();assert s.count(a)==n,(f,s.count(a),a);p.write_text(s.replace(a,b))
edit('flow.py','        c = self.control\n        await authorize(c.hass,context)\n        async with self.tank.lock:', '        c = self.control\n        requested_generation = c.generation\n        await authorize(c.hass,context)\n        async with self.tank.lock:')
edit('flow.py','                if guard:\n                    guard()\n                if not self.tank.active', '                if guard:\n                    guard()\n                if requested_generation != c.generation:\n                    raise ServiceValidationError("revoked")\n                if not self.tank.active')
edit('flow.py',"                self.run_plan = deepcopy(dict(run_id=c.run_id", "                self.bounds = deepcopy({k:o.get(k,{}) for k in ('dosing_parameters','acid_parameters','mix_parameters','safety_parameters')})\n                self.params = dict(self.tank.parameters)\n                self.midpoints = {}\n                self.run_plan = deepcopy(dict(run_id=c.run_id")
edit('flow.py','    def stage(self,s):','    def tighten(self):\n        if not self.active:\n            return\n        minimum = {"pulse_seconds","max_total_on_seconds","max_pulses","flow_timeout_seconds","sample_wait_timeout_seconds","ec_danger_high"}\n        maximum = {"safe_min_level_m","ph_danger_low","post_mix_seconds","stable_samples","stable_interval_seconds"}\n        for namespace, values in self.bounds.items():\n            live = self.tank.entry.options.get(namespace,{})\n            for key,value in list(values.items()):\n                if key in live and key in minimum:\n                    values[key] = min(value,live[key])\n                elif key in live and key in maximum:\n                    values[key] = max(value,live[key])\n        for key in ("refill_timeout","ph_timeout","ec_timeout","mix_duration","level_high"):\n            self.params[key] = min(self.params[key],self.tank.parameters[key])\n        from decimal import Decimal\n        for role,source,direction in (("nutrient","ec",1),("acid","ph",-1)):\n            value = float(direction*(Decimal(str(self.tank.parameters[source+"_low"]))+Decimal(str(self.tank.parameters[source+"_high"])))/2)\n            original = float(direction*(Decimal(str(self.params[source+"_low"]))+Decimal(str(self.params[source+"_high"])))/2)\n            self.midpoints[role] = min(self.midpoints.get(role,original),value)\n\n    def settings(self,role):\n        return deepcopy(self.bounds["dosing_parameters"] if role == "nutrient" else {**self.bounds["acid_parameters"],**self.bounds["safety_parameters"]} if role == "acid" else self.bounds["mix_parameters"])\n\n    def stage(self,s):')
edit('flow.py',"                c.receipts[request_id] = (time.monotonic(),dict(result))\n                self.tank.publish()", "                c.receipts[request_id] = (time.monotonic(),dict(result))\n                while len(c.receipts) > 64:\n                    c.receipts.pop(next(iter(c.receipts)))\n                self.tighten()\n                self.tank.publish()")
edit('flow.py',"        self.clock = time.monotonic\n        self.circ_lock", "        self.clock = time.monotonic\n        self.weekday = lambda: DAYS[dt_util.now().weekday()]\n        self.circ_lock")
edit('flow.py',"            if DAYS[dt_util.now().weekday()] not in self.run_plan['allowed_weekdays'][name]:\n                self.settle(name,'skipped_weekday')\n                return True\n", "")
edit('flow.py',"            stage = self.stage(name)\n            if name == 'refill':", "            if self.weekday() not in self.run_plan['allowed_weekdays'][name]:\n                self.settle(name,'skipped_weekday')\n                return True\n            stage = self.stage(name)\n            if name == 'refill':")
edit('control.py','                if DAYS[dt_util.now().weekday()] not in days.get(stage.role, DAYS):','                day = self.flow.weekday() if self.flow.active else DAYS[dt_util.now().weekday()]\n                if day not in days.get(stage.role, DAYS):')
# Native descriptor grammar is explicit, not guessed by the consumer.
p = R/'services.yaml'
s = p.read_text(encoding='utf8')
for name, fields in {
    'apply_flow_plan_v5': ('config_entry_id','expected_revision','expected_flow_plan_revision','flow_plan','allowed_weekdays'),
    'preview_flow_plan_v5': ('config_entry_id','expected_revision','expected_flow_plan_revision','flow_plan','allowed_weekdays','weekday'),
    'apply_control_settings_v5': ('config_entry_id','expected_revision','parameters','dosing_parameters','acid_parameters','mix_parameters','safety_parameters'),
}.items():
    assert name+':' not in s
    s += '\n\n'+name+':\n  name: '+name+'\n  description: Explicit schema5 transaction; no commissioning or automatic start. CAS conflicts do not write.\n  fields:\n'
    for field in fields:
        s += '    '+field+':\n      required: true\n      selector:\n'
        if field == 'config_entry_id':
            s += '        config_entry:\n          integration: uninus_nutriculture\n'
        elif field.startswith('expected_'):
            s += '        number:\n          min: 0\n          step: 1\n          mode: box\n'
        elif field == 'weekday':
            s += '        select:\n          options: [mon, tue, wed, thu, fri, sat, sun]\n'
        else:
            s += '        object:\n'
p.write_text(s,encoding='utf8')
edit('control.py','        if self.flow.active:\n            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage):\n                if stage.owns_io:\n                    stage.tighten()','        if self.flow.active:\n            self.flow.tighten()\n            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage):\n                if stage.owns_io:\n                    stage.tighten()')
edit('control.py','            self.fault = None\n            self.acid_stage.revoked', '            self.fault = None\n            if self.flow.run_plan:\n                self.flow.outcome = None\n            self.acid_stage.revoked')
edit('nutrient.py','    def live_settings(self):\n        options = self.tank.entry.options','    def live_settings(self):\n        if self.control.flow.active:\n            return self.control.flow.settings(self.role)\n        options = self.tank.entry.options')
edit('nutrient.py','    def live_midpoint(self):\n        from decimal import Decimal','    def live_midpoint(self):\n        if self.control.flow.active and self.role in self.control.flow.midpoints:\n            return self.control.flow.midpoints[self.role]\n        from decimal import Decimal')
edit('nutrient.py','if self.control.running and hasattr(self, "deadline")','if self.owns_io and hasattr(self, "deadline")')
edit('nutrient.py','            self.control.running\n            and hasattr(self, "stage_deadline")','            self.owns_io\n            and hasattr(self, "stage_deadline")')
edit('nutrient.py','        self.stage_deadline = self.clock() + self.tank.parameters[self.source + "_timeout"] * 60','        params = self.control.flow.params if self.control.flow.active else self.tank.parameters\n        self.stage_deadline = self.clock() + params[self.source + "_timeout"] * 60')
edit('mix.py','        if value < self.tank.entry.options["mix_parameters"]["safe_min_level_m"]:', '        settings = self.control.flow.settings("mix") if self.control.flow.active else self.tank.entry.options["mix_parameters"]\n        if value < settings["safe_min_level_m"]:')
edit('mix.py','< self.tank.entry.options["mix_parameters"]["safe_min_level_m"]','< (self.control.flow.settings("mix") if self.control.flow.active else self.tank.entry.options["mix_parameters"])["safe_min_level_m"]')
edit('mix.py','        config = self.tank.entry.options["control"]\n        self.started = self.clock()', '        config = self.tank.entry.options["control"]\n        settings = self.control.flow.settings("mix") if self.control.flow.active else self.tank.entry.options["mix_parameters"]\n        params = self.control.flow.params if self.control.flow.active else self.tank.parameters\n        self.started = self.clock()')
edit('mix.py','            self.tank.entry.options["mix_parameters"]["flow_timeout_seconds"],\n            config', '            settings["flow_timeout_seconds"],\n            config')
edit('mix.py','        self.end = self.started + self.tank.parameters["mix_duration"] * 60', '        self.end = self.started + params["mix_duration"] * 60')
edit('flow.py',"        self.high = c.tank.parameters['level_high']\n        self.deadline = self.started + c.tank.parameters['refill_timeout'] * 60", "        self.high = self.flow.params['level_high']\n        self.deadline = self.started + self.flow.params['refill_timeout'] * 60\n        self.cleaning = False")
