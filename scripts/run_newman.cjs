const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const newman = require('newman');
const [mode, baseUrl, directory] = process.argv.slice(2);
if (!['normal', 'expiry'].includes(mode) || !baseUrl || !directory) throw Error('Expected mode, base URL and report directory');
const collection = JSON.parse(fs.readFileSync(path.join(root, 'postman/collection.json'), 'utf8'));
collection.item = collection.item.filter(item => mode === 'expiry' ? item.name === '过期鉴权' : item.name !== '过期鉴权');
const environment = JSON.parse(fs.readFileSync(path.join(root, 'postman', mode === 'expiry' ? 'environment.short-lived.json' : 'environment.example.json'), 'utf8'));
newman.run({collection, environment, envVar: [{key: 'base_url', value: baseUrl}], iterationCount: 2,
  timeoutRequest: 5000, timeoutScript: 10000, reporters: ['cli', 'json', 'junit'],
  reporter: {json: {export: path.join(directory, 'newman-results.json')}, junit: {export: path.join(directory, 'newman-results.xml')}}},
  (error, summary) => {if (error) console.error(error.message); process.exitCode = error || summary.run.failures.length ? 1 : 0;});
