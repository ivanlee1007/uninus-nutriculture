'use strict';
// Supplementary unit probes: real shipped prototype, no DOM renderer replacement.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const elements = new Map();
const context = {HTMLElement:class {},window:{},customElements:{get:k=>elements.get(k),define:(k,v)=>elements.set(k,v)},console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../uninus-nutriculture-card.js'),'utf8'),context);
const C = elements.get('uninus-nutriculture-card');
const row = {key:'ph_low',unit:'',input:{value:'5.55'}};
function owner() {
  const status = {state:'within_range',attributes:{schema_version:1,mode:'shadow',parameter_entities:{ph_low:'number.actual_ph'}}};
  return {status:()=>status,_hass:{states:{'number.actual_ph':{state:'5.4',attributes:{min:0,max:14,step:.01,unit_of_measurement:'pH'}}}}};
}
test('target uses exact mapped Number and native metadata',()=>{
  const got = C.prototype.target.call(owner(),row);
  assert.equal(got.id,'number.actual_ph'); assert.equal(got.min,0); assert.equal(got.max,14); assert.equal(got.step,.01); assert.equal(got.unit,'pH');
});
test('schema/mode unavailable never yield a writable target',()=>{
  for (const mutate of [o=>o.status().attributes.schema_version=2,o=>o.status().attributes.mode='active',o=>o.status().state='unavailable']) {
    const o=owner();mutate(o);assert.ok(C.prototype.target.call(o,row).error);
  }
});
test('invalid mappings and unavailable Number fail closed',()=>{
  for (const id of ['switch.pump','number.BAD','number.a extra',null,'']) {
    const o=owner();o.status().attributes.parameter_entities.ph_low=id;assert.ok(C.prototype.target.call(o,row).error);
  }
  const o=owner();o._hass.states['number.actual_ph'].state='unavailable';assert.ok(C.prototype.target.call(o,row).error);
});
test('finite range and step validation includes exact boundary',()=>{
  const target={min:.8,max:.9,step:.01};
  for (const value of ['.8','.85','.9']) assert.equal(C.prototype.valid.call({}, {input:{value}},target),true,value);
  for (const value of ['',null,'NaN','Infinity','.79','.91','.855']) assert.equal(C.prototype.valid.call({}, {input:{value}},target),false,String(value));
});
test('v2 stub selects actual control sensor, never an arbitrary or unknown contract',()=>{
  const valid={state:'idle',attributes:{schema_version:2,mode:'control',flow_state:'idle'}};
  assert.equal(C.getStubConfig({states:{'sensor.other':{attributes:{}},'sensor.control_actual':valid}}).entity,'sensor.control_actual');
  assert.equal(C.getStubConfig({states:{'sensor.future':{attributes:{schema_version:3,mode:'control'}}}}).entity,'sensor.uninus_nutriculture_status');
});
test('v2 Number target accepts control only, preserving v1 shadow validation',()=>{
  const o=owner();Object.assign(o.status().attributes,{schema_version:2,mode:'control',flow_state:'idle'});o.status().state='idle';
  assert.equal(C.prototype.target.call(o,row).id,'number.actual_ph');
  o.status().attributes.mode='shadow';assert.ok(C.prototype.target.call(o,row).error);
});
test('native control resolves exact domains, fresh service and capability',()=>{
  const o=owner(), r={key:'flow_run',domain:'switch'};
  Object.assign(o.status().attributes,{schema_version:2,mode:'control',flow_state:'idle',capabilities:{refill:true},control_entities:{flow_run:'switch.native_run'}});o.status().state='idle';
  o._hass.states['switch.native_run']={state:'off'};
  assert.equal(C.prototype.controlTarget.call(o,r).service,'turn_on');
  o._hass.states['switch.native_run'].state='on';assert.equal(C.prototype.controlTarget.call(o,r).service,'turn_off');
  for(const id of ['button.native_run','switchXnative_run','switch.BAD',null]){o.status().attributes.control_entities.flow_run=id;assert.ok(C.prototype.controlTarget.call(o,r).error)}
  o.status().attributes.control_entities.flow_run='switch.native_run';o.status().attributes.capabilities.refill=false;assert.ok(C.prototype.controlTarget.call(o,r).error);
});
test('native Button unknown is usable but unavailable and wrong domain are not',()=>{
  const o=owner(), r={key:'emergency_stop',domain:'button'};
  Object.assign(o.status().attributes,{schema_version:2,mode:'control',flow_state:'fault',control_entities:{emergency_stop:'button.native_stop'}});o.status().state='fault';
  o._hass.states['button.native_stop']={state:'unknown'};
  assert.equal(C.prototype.controlTarget.call(o,r).service,'press');
  o._hass.states['button.native_stop'].state='unavailable';assert.ok(C.prototype.controlTarget.call(o,r).error);
});
test('registration is idempotent with a second resource evaluation',()=>{
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../uninus-nutriculture-card.js'),'utf8'),context);
  assert.equal(elements.size,2);assert.equal(context.window.customCards.length,1);
  assert.equal(elements.get('uninus-nutriculture-card'),C);
});
