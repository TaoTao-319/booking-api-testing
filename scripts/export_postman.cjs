const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');
const yaml = require('yaml');
const base = path.join(root, 'postman/collections/预约接口测试');
const read = file => yaml.parse(fs.readFileSync(file, 'utf8'));
const pairs = value => Array.isArray(value) ? value : Object.entries(value || {}).map(([key, value]) => ({key, value}));
const sources = [];
function convert(dir) {
  const definition = read(path.join(dir, '.resources/definition.yaml'));
  const entries = fs.readdirSync(dir, {withFileTypes: true}).filter(e => e.name !== '.resources');
  const items = entries.filter(e => e.isDirectory() || e.name.endsWith('.request.yaml')).map(e => {
    const file = path.join(dir, e.name);
    if (e.isDirectory()) {
      const data = convert(file);
      return {order: data.order, item: {name: data.name || e.name, item: data.item, auth: {type: 'noauth'}}};
    }
    const d = read(file);
    if (d.auth && d.auth.type !== 'noauth') throw Error('Unsupported authorization: ' + file);
    const request = {method: d.method, url: d.url, auth: {type: 'noauth'},
      header: pairs(d.headers).map(h => ({key: h.key, value: String(h.value), disabled: h.disabled === true || h.enabled === false}))};
    if (d.queryParams) {
      request.url = d.url.split('?')[0] + '?' + pairs(d.queryParams)
        .filter(q => q.enabled !== false && !q.disabled).map(q => `${q.key}=${q.value}`).join('&');
    }
    if (d.body) {
      if (!['json', 'text'].includes(d.body.type)) throw Error('Unsupported body: ' + file);
      request.body = {mode: 'raw', raw: d.body.content, options: {raw: {language: d.body.type}}};
    }
    const event = (d.scripts || []).filter(s => s.enabled !== false).map(s => {
      if (!['beforeRequest', 'afterResponse'].includes(s.type)) throw Error('Unsupported script: ' + file);
      new vm.Script(s.code, {filename: file});
      return {listen: s.type === 'beforeRequest' ? 'prerequest' : 'test', script: {type: 'text/javascript', exec: s.code.split('\n')}};
    });
    if (!event.some(e => e.listen === 'test' && e.script.exec.join('\n').includes('pm.test'))) throw Error('Missing tests: ' + file);
    sources.push({file: path.relative(root, file).replaceAll('\\', '/'), sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
    return {order: d.order || 0, item: {name: d.name || e.name.replace('.request.yaml', ''), request, event}};
  }).sort((a, b) => a.order - b.order);
  return {...definition, item: items.map(e => e.item)};
}
const native = convert(base);
const collection = {info: {name: native.name, schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'}, auth: {type: 'noauth'}, item: native.item};
const write = (file, data) => fs.writeFileSync(path.join(root, file), JSON.stringify(data, null, 2) + '\n');
write('postman/collection.json', collection);
for (const [name, file] of [['本地预约服务', 'environment.example.json'], ['短有效期预约服务', 'environment.short-lived.json']]) {
  const environment = read(path.join(root, `postman/environments/${name}.environment.yaml`));
  write('postman/' + file, {name: environment.name, _postman_variable_scope: 'environment', values: environment.values.map(v => ({key: v.key,
    value: ['base_url', 'username', 'password'].includes(v.key) ? v.value : '', type: 'default', enabled: v.enabled !== false}))});
}
write('postman/export-manifest.json', {request_count: sources.length, sources});
console.log(`Exported ${sources.length} requests and two environments.`);
