/* UNiNUS Nutriculture Card 0.2.0-alpha.1 — P1 shadow / P2 mapped native controls. */
(() => {
  'use strict';
  const TAG = 'uninus-nutriculture-card';
  const finite = value => (typeof value === 'number' || (typeof value === 'string' && value.trim() !== '')) && Number.isFinite(Number(value));
  const text = (node, value) => { const next = String(value ?? ''); if (node.textContent !== next) node.textContent = next; };
  const make = (tag, value, className) => { const el = document.createElement(tag); if (value !== undefined) text(el, value); if (className) el.className = className; return el; };
  const PARAMETERS = [
    ['level_low','液位下限',2.25,'m'],['level_high','液位上限',2.4,'m'],
    ['ph_low','pH 下限',5.4,''],['ph_high','pH 上限',5.8,''],
    ['ec_low','EC 下限',0.8,'mS/cm'],['ec_high','EC 上限',0.9,'mS/cm'],
    ['refill_timeout','補水逾時',190,'min'],['ec_timeout','EC 逾時',90,'min'],
    ['ph_timeout','pH 逾時',190,'min'],['mix_duration','混合時間',10,'min']
  ];
  const FLOW_STATES = ['uncommissioned','disabled','idle','starting','refilling','stopping','completed','aborted','fault'];
  const isShadow = status => status?.attributes?.schema_version === 1 && status.attributes.mode === 'shadow';
  const isControl = status => status?.attributes?.schema_version === 2 && status.attributes.mode === 'control';
  const writable = status => (isShadow(status) && ['within_range','out_of_range','invalid'].includes(status.state)) || (isControl(status) && FLOW_STATES.includes(status.state) && status.attributes.flow_state === status.state);
  const style = `
    :host{display:block;min-width:0;color:var(--primary-text-color,#213b48);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
    *{box-sizing:border-box}ha-card{display:block;border:1px solid var(--divider-color,#d9e4e7);border-radius:var(--ha-card-border-radius,16px);background:var(--ha-card-background,var(--card-background-color,#fff));padding:18px;overflow-wrap:anywhere}
    h2{font-size:19px;line-height:1.35;margin:0}header p{color:var(--secondary-text-color,#607782);font-size:13px;margin:4px 0 12px}.badge{display:inline-block;color:var(--primary-color,#277b86);background:var(--secondary-background-color,#edf5f6);border-radius:8px;padding:4px 8px;font-size:12px}
    .safety{border-left:3px solid var(--primary-color,#277b86);padding:8px 10px;margin:12px 0;font-size:13px;background:var(--secondary-background-color,#edf5f6)}
    .tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.tile{min-width:0;background:var(--secondary-background-color,#f2f7f8);padding:12px 8px;border-radius:10px}.tile span{display:block;color:var(--secondary-text-color,#607782);font-size:12px}.tile strong{display:block;font-size:22px;font-variant-numeric:tabular-nums;margin:6px 0}.tile small{font-size:11px;overflow-wrap:anywhere}
    .quality{font-size:13px;margin:12px 0 0;white-space:pre-line}.quality.warn{color:var(--error-color,#a44e28)}
    details{margin-top:16px;border-top:1px solid var(--divider-color,#d9e4e7);padding-top:12px}summary{cursor:pointer;font-size:14px;font-weight:600;min-height:32px}details>p{font-size:12px;color:var(--secondary-text-color,#607782)}
    .param{display:grid;grid-template-columns:minmax(0,1fr) minmax(70px,110px) 64px;gap:6px 10px;align-items:center;padding:10px 0;border-top:1px solid var(--divider-color,#d9e4e7)}.param label{font-size:13px;min-width:0}.param small{display:block;font-size:11px;color:var(--secondary-text-color,#607782);margin-top:3px}.param .message{grid-column:1/-1;font-size:12px;white-space:pre-line;color:var(--secondary-text-color,#607782)}
    input,button{font:inherit;min-width:0;max-width:100%;border-radius:7px;padding:9px 7px;border:1px solid var(--divider-color,#cddce1);color:inherit;background:var(--card-background-color,#fff)}input{width:100%;font-size:14px}button{cursor:pointer;font-size:13px;color:var(--primary-color,#277b86)}button:disabled{cursor:not-allowed;opacity:.5}:focus-visible{outline:2px solid var(--primary-color,#277b86);outline-offset:2px}
    .control{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:9px 0;border-top:1px solid var(--divider-color,#d9e4e7)}.control button{min-width:64px;min-height:40px}.control small{grid-column:1/-1;white-space:pre-line;font-size:12px}.control p,[data-control-status]{white-space:pre-line}
    @media(max-width:360px){ha-card{padding:12px}.tile strong{font-size:20px}.tile{padding:10px 6px}}
  `;
  class NutricultureCard extends HTMLElement {
    constructor() {
      super(); this.attachShadow({mode:'open'});
      const css = make('style', style); this.root = make('ha-card');
      const header = make('header'); this.heading = make('h2','UNiNUS Nutriculture');
      this.badge = make('span','影子監測','badge');
      header.append(this.heading,make('p','養液控制'),this.badge);
      this.safety = make('div','不控制設備 · 尚未提供灌溉許可','safety');
      const tiles = make('section',undefined,'tiles'); tiles.setAttribute('aria-label','即時來源讀值');
      this.readings = {};
      for (const [key,label] of [['ph','pH 酸鹼值'],['ec','EC 導電度'],['level','液位']]) {
        const tile = make('div',undefined,'tile'); tile.dataset.reading = key;
        const value = make('strong','—'), unit = make('small','');
        tile.append(make('span',label),value,unit); tiles.append(tile); this.readings[key] = {value,unit};
      }
      this.quality = make('div','','quality'); this.quality.setAttribute('role','status');
      this.root.append(header,this.safety,tiles,this.quality); this.shadowRoot.append(css,this.root);
      this.rows = new Map(); this.flights = new Map();
      this.controls = make('section'); this.controls.dataset.controls = '';
      this.controlStatus = make('p'); this.controlStatus.dataset.controlStatus = ''; this.controlStatus.setAttribute('role','status');
      this.unsupported = make('p'); this.unsupported.dataset.unsupported = '';
      this.controls.append(this.controlStatus,this.unsupported);
      this.controlRows = new Map();
      for (const [key,label,domain] of [['automation_enabled','自動化總開關','switch'],['refill_enabled','補水子開關','switch'],['flow_run','整輪運行','switch'],['emergency_stop','急停','button'],['reset_fault','復歸','button']]) {
        const el = make('div',undefined,'control'); el.dataset.control = key;
        const caption = make('span'), button = make('button',label), message = make('small');
        button.type = 'button'; button.setAttribute('aria-label',label); message.setAttribute('role','status');
        const row = {key,label,domain,el,caption,button,message,error:''};
        button.addEventListener('click',()=>this.invokeControl(row));
        el.append(caption,button,message); this.controls.append(el); this.controlRows.set(key,row);
      }
      this.details = make('details');
      this.parameterHelp = make('p','每次僅儲存一項，不提供群組原子更新。時間參數僅儲存，不控制設備。');
      this.details.append(make('summary','參數調整 · 單項儲存'),this.parameterHelp);
      for (const [key,label,initial,unit] of PARAMETERS) {
        const el = make('div',undefined,'param'); el.dataset.param = key;
        const caption = make('label',label); caption.htmlFor = key;
        const metadata = make('small'); caption.append(metadata);
        const input = make('input'); input.type = 'number'; input.id = key; input.inputMode = 'decimal';
        const button = make('button','儲存'); button.type = 'button'; button.setAttribute('aria-label',`儲存 ${label}`);
        const message = make('div','','message'); message.setAttribute('role','status');
        const row = {key,el,metadata,input,button,message,initial,unit,dirty:false,pending:false,error:''};
        input.addEventListener('input',()=>{row.dirty = true; row.error = ''; this.updateRows();});
        button.addEventListener('click',()=>this.save(row));
        el.append(caption,input,button,message); this.rows.set(key,row); this.details.append(el);
      }
      this.root.append(this.details); this.updateRows();
    }
    static getConfigElement() { return document.createElement(`${TAG}-editor`); }
    static getStubConfig(hass) {
      const entity = Object.keys(hass?.states ?? {}).find(id => /^sensor\.[a-z0-9_]+$/.test(id) && (isShadow(hass.states[id]) || isControl(hass.states[id])));
      return {entity:entity ?? 'sensor.uninus_nutriculture_status',show_parameters:true};
    }
    getCardSize() { return this.details.isConnected && this.details.open ? 12 : 4; }
    connectedCallback() { this.update(); }
    disconnectedCallback() { this.invalidate(); }
    invalidate() {
      this.epoch = (this.epoch ?? 0) + 1;
      for (const row of this.rows.values()) { row.operation = null; row.pending = false; }
      for (const row of this.controlRows.values()) { row.operation = null; row.error = ''; }
    }
    setConfig(config) {
      if (!config || typeof config.entity !== 'string' || !/^sensor\.[a-z0-9_]+$/.test(config.entity)) throw new Error('請選擇狀態 sensor Entity');
      this.invalidate();
      if (this.config?.entity !== config.entity) {
        for (const row of this.rows.values()) { row.dirty = false; row.error = ''; }
        this.details.open = false;
      }
      this.config = {...config};
      if (config.show_parameters === false) this.details.remove();
      else if (this.details.parentNode !== this.root) this.root.append(this.details);
      this.update();
    }
    set hass(hass) { this._hass = hass; this.update(); }
    get hass() { return this._hass; }
    status() { return this._hass?.states?.[this.config?.entity]; }
    target(row) {
      const status = this.status();
      if (!writable(status)) return {error:'狀態缺失或不相容；禁止儲存'};
      const id = status.attributes.parameter_entities?.[row.key];
      if (typeof id !== 'string' || !/^number\.[a-z0-9_]+$/.test(id)) return {error:'Number 對應無效；禁止儲存'};
      const state = this._hass?.states?.[id];
      if (!finite(state?.state)) return {error:'Number 缺失或無法使用；禁止儲存'};
      const {min,max,step,unit_of_measurement:unit} = state.attributes ?? {};
      if (![min,max,step].every(finite) || Number(min)>Number(max) || Number(step)<=0) return {error:'Number metadata 無效；禁止儲存'};
      return {id,state,min:Number(min),max:Number(max),step:Number(step),unit:unit ?? row.unit};
    }
    valid(row,target) {
      if (target.error || !finite(row.input.value)) return false;
      const value = Number(row.input.value), ticks = (value-target.min)/target.step;
      return value>=target.min && value<=target.max && Math.abs(ticks-Math.round(ticks))<1e-6;
    }
    updateRows() {
      if (!this.rows) return;
      for (const row of this.rows.values()) {
        const target = this.target(row);
        if (row.boundTarget !== target.id) {
          if (row.dirty) row.error = 'Number 對應已變更；舊草稿已清除，請重新輸入';
          row.boundTarget = target.id; row.dirty = false; row.pending = false; row.operation = null;
        }
        if (!row.dirty && !row.pending) {
          const value = target.state?.state ?? this.status()?.attributes?.parameters?.[row.key];
          const next = finite(value) ? String(value) : '';
          if (row.input.value !== next) row.input.value = next;
        }
        for (const key of ['min','max','step']) {
          if (!target.error) row.input.setAttribute(key,String(target[key])); else row.input.removeAttribute(key);
        }
        text(row.metadata,target.error ? `預設 ${row.initial} ${row.unit}` : `${target.min}–${target.max} ${target.unit} · 間距 ${target.step}`);
        row.input.disabled = row.pending || !!target.error;
        row.button.disabled = row.pending || this.flights.has(target.id) || !row.dirty || !this.valid(row,target);
        text(row.button,row.pending ? '儲存中' : '儲存');
        text(row.message,target.error || row.error || (row.dirty && !this.valid(row,target) ? '請輸入範圍內、符合間距的有限數值' : ''));
      }
    }
    async save(row) {
      const target = this.target(row);
      if (row.boundTarget !== target.id) { this.updateRows(); return; }
      if (!this.isConnected || this.config?.show_parameters === false || this.flights.has(target.id) || row.pending || !row.dirty || !this.valid(row,target) || !this._hass?.callService) return;
      // Snapshot ownership and payload before the first deferred boundary.
      const op = {epoch:this.epoch,entity:this.config.entity,target:target.id,value:Number(row.input.value)};
      this.flights.set(op.target,op);
      row.operation = op; row.pending = true; row.error = ''; this.updateRows();
      const current = () => this.isConnected && this.epoch === op.epoch && row.operation === op;
      try {
        await this._hass.callService('number','set_value',{entity_id:op.target,value:op.value});
        if (!current()) return;
        row.dirty = false; row.error = '已送出單項儲存；以 Entity 讀回值為準';
      } catch (error) {
        if (!current()) return;
        row.error = `儲存失敗：${error?.message ?? String(error)}`;
      } finally {
        if (this.flights.get(op.target) === op) this.flights.delete(op.target);
        if (current()) { row.operation = null; row.pending = false; this.updateRows(); }
        else if (this.isConnected) {
          // Release only the transport lock; never reconcile new-scope drafts/notices.
          for (const candidate of this.rows.values()) {
            const next = this.target(candidate);
            candidate.button.disabled = candidate.pending || this.flights.has(next.id) || !candidate.dirty || !this.valid(candidate,next);
          }
        }
      }
    }
    controlTarget(row) {
      const status = this.status();
      if (!isControl(status) || !writable(status)) return {error:'控制狀態缺失或不相容；禁止操作'};
      if (['refill_enabled','flow_run'].includes(row.key) && status.attributes.capabilities?.refill !== true) return {error:'補水尚未支援；禁止操作'};
      const id = status.attributes.control_entities?.[row.key];
      if (typeof id !== 'string' || !new RegExp(`^${row.domain}\\.[a-z0-9_]+$`).test(id)) return {error:'控制 Entity 對應無效；禁止操作'};
      const state = this._hass?.states?.[id];
      if (!state || state.state === 'unavailable' || (row.domain === 'switch' && !['on','off'].includes(state.state)) || typeof state.state !== 'string') return {error:'控制 Entity 缺失或無法使用；禁止操作'};
      return {id,state:state.state,service:row.domain === 'button' ? 'press' : state.state === 'on' ? 'turn_off' : 'turn_on'};
    }
    updateControls() {
      for (const row of this.controlRows.values()) {
        const target = this.controlTarget(row);
        if (row.boundTarget !== target.id) { row.boundTarget = target.id; row.error = ''; row.operation = null; }
        text(row.caption,`${row.label} · ${target.state ?? '不可用'} `);
        row.button.disabled = !this.isConnected || !!target.error || this.flights.has(target.id);
        text(row.button,row.domain === 'button' ? row.label : target.state === 'on' ? '關閉' : '開啟');
        text(row.message,target.error || row.error);
      }
    }
    async invokeControl(row) {
      const target = this.controlTarget(row);
      if (row.boundTarget !== target.id) { this.updateControls(); return; }
      if (!this.isConnected || target.error || this.flights.has(target.id) || !this._hass?.callService) return;
      const op = {epoch:this.epoch,entity:this.config.entity,target:target.id};
      this.flights.set(op.target,op); row.operation = op; row.error = ''; this.updateControls();
      const current = () => this.isConnected && this.epoch === op.epoch && row.operation === op && this.controlTarget(row).id === op.target;
      try {
        await this._hass.callService(row.domain,target.service,{entity_id:op.target});
        if (current()) row.error = '已送出操作；以 Entity 讀回值為準';
      } catch (error) {
        if (current()) row.error = `操作失敗：${error?.message ?? String(error)}`;
      } finally {
        if (this.flights.get(op.target) === op) this.flights.delete(op.target);
        if (current()) row.operation = null;
        if (this.isConnected) this.updateControls();
      }
    }
    update() {
      text(this.heading,this.config?.title ?? 'UNiNUS Nutriculture');
      const status = this.status();
      for (const [key, nodes] of Object.entries(this.readings)) {
        const source = this._hass?.states?.[status?.attributes?.source_entities?.[key]];
        text(nodes.value,finite(source?.state) ? Number(source.state).toLocaleString(undefined,{maximumFractionDigits:3}) : '—');
        text(nodes.unit,source?.attributes?.unit_of_measurement ?? ({ph:'pH',ec:'mS/cm',level:'m'}[key]));
      }
      const control = isControl(status), compatible = isShadow(status) || control;
      text(this.parameterHelp,control ? '每次僅儲存一項，不提供群組原子更新。補水門檻與逾時由後端即時校驗；加養／加酸／獨立混合尚未支援。' : '每次僅儲存一項，不提供群組原子更新。時間參數僅儲存，不控制設備。');
      text(this.badge,control ? '控制模式 · P2 補水' : '影子監測');
      text(this.safety,control ? '僅補水控制 · 後端安全校驗 · 尚未提供灌溉許可' : '不控制設備 · 尚未提供灌溉許可');
      if (control) {
        if (this.controls.parentNode !== this.root) this.root.insertBefore(this.controls,this.details.parentNode === this.root ? this.details : null);
        const a = status.attributes;
        text(this.controlStatus,`流程：${a.flow_state ?? '未知'} · Sensor：${status.state}\n故障：${a.fault ?? '無'} · 本輪：${a.run_id ?? '無'}`);
        text(this.unsupported,'加養／加酸／獨立混合：尚未支援（P2 不執行）');
      } else this.controls.remove();
      const labels = {within_range:'讀值在範圍內',out_of_range:'讀值超出範圍',invalid:'來源資料無效'};
      const warning = !compatible ? '狀態缺失或不相容：僅支援 schema 1 / shadow 或 schema 2 / control；禁止儲存。' : control ? (writable(status) ? '控制狀態以原生 Entity 讀回為準' : '未知或不一致狀態；禁止儲存。') : labels[status.state] ?? '未知狀態；禁止儲存。';
      const reasons = Array.isArray(status?.attributes?.reasons) ? status.attributes.reasons.map(String) : [];
      const blocked = Array.from(this.rows.values()).filter(row=>this.target(row).error).length;
      const parameterWarning = compatible && blocked ? `${blocked} 項參數無法儲存；請展開參數檢查 Number Entity。` : '';
      text(this.quality,[warning,parameterWarning,...reasons].filter(Boolean).join('\n'));
      this.quality.classList.toggle('warn',!compatible || status.state !== 'within_range' || blocked>0);
      this.updateRows(); this.updateControls();
    }
  }
  class NutricultureEditor extends HTMLElement {
    constructor() {
      super(); this.attachShadow({mode:'open'});
      this.shadowRoot.append(make('style',`${style}label{display:block;margin:12px 0;font-size:14px}select{width:100%;max-width:100%;padding:10px;box-sizing:border-box;color:inherit;background:var(--card-background-color,#fff)}input[type=checkbox]{width:auto;margin-right:8px}`));
      this.entityInput = make('select'); this.entityInput.name = 'entity';
      this.titleInput = make('input'); this.titleInput.name = 'title'; this.titleInput.type = 'text';
      this.showInput = make('input'); this.showInput.name = 'show_parameters'; this.showInput.type = 'checkbox';
      for (const [label,input] of [['狀態 Entity',this.entityInput],['標題',this.titleInput],['顯示參數調整',this.showInput]]) {
        const field = make('label',label); field.append(input); this.shadowRoot.append(field);
      }
      this.shadowRoot.append(make('p','schema 1 / shadow：不控制設備；schema 2 / control：原生補水控制。兩者皆尚未提供灌溉許可。'));
      this.entityInput.addEventListener('change',()=>this.change('entity',this.entityInput.value));
      this.titleInput.addEventListener('input',()=>this.change('title',this.titleInput.value));
      this.showInput.addEventListener('change',()=>this.change('show_parameters',this.showInput.checked));
    }
    setConfig(config) {
      this.config = structuredClone(config ?? {});
      this.titleInput.value = this.config.title ?? '';
      this.showInput.checked = this.config.show_parameters !== false;
      this.options();
    }
    set hass(hass) { this._hass = hass; this.options(); }
    options() {
      const ids = Object.keys(this._hass?.states ?? {}).filter(id=>/^sensor\.[a-z0-9_]+$/.test(id));
      if (this.config?.entity && !ids.includes(this.config.entity)) ids.push(this.config.entity);
      ids.sort(); const signature = JSON.stringify(ids);
      if (this.optionSignature !== signature) {
        this.optionSignature = signature; this.entityInput.replaceChildren(make('option','請選擇狀態 sensor'));
        this.entityInput.firstChild.value = '';
        for (const id of ids) { const option = make('option',id); option.value = id; this.entityInput.append(option); }
      }
      this.entityInput.value = this.config?.entity ?? '';
    }
    change(key,value) {
      this.config = {...this.config,[key]:value};
      this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:structuredClone(this.config)},bubbles:true,composed:true}));
    }
  }
  if (!customElements.get(`${TAG}-editor`)) customElements.define(`${TAG}-editor`,NutricultureEditor);
  if (!customElements.get(TAG)) customElements.define(TAG,NutricultureCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some(card=>card.type === TAG)) window.customCards.push({type:TAG,name:'UNiNUS Nutriculture / 養液控制',description:'P1 影子監測／P2 原生補水控制與單項參數儲存；尚未提供灌溉許可',preview:true});
})();
