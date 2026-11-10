// Small behaviour checks without network or an installed browser.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

function appContext() {
  const nodes = new Map();
  function node() {
    return {textContent:'', hidden:false, value:'', dataset:{}, children:[],
      addEventListener(){}, setAttribute(){}, hasAttribute(){return false;},
      replaceChildren(...children){this.children=children;}, append(...children){this.children.push(...children);},
      querySelector(){return null;}, querySelectorAll(){return [];}, focus(){}};
  }
  const getNode = id => {if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  const events = {};
  const context=vm.createContext({document:{documentElement:{},querySelectorAll(){return [];},getElementById:getNode,createElement:node,createTextNode:node},
    window:{addEventListener(name,handler){events[name]=handler;}}, URL, setTimeout, clearTimeout,
    fetch(){throw new Error('Unexpected network call');}});
  vm.runInContext(readFileSync(join(__dirname,'../app/static/app.js'),'utf8'),context);
  return {context,getNode,events,run:code=>vm.runInContext(code,context)};
}

test('an invalid map point clears an earlier valid location',()=>{
  const app=appContext();
  app.run("setLocation(50,8,'Mainz')");
  assert.equal(app.run('selected.label'),'Mainz');
  app.run('setLocation(60,8)');
  assert.equal(app.run('selected'),null);
  assert.match(app.getNode('location').textContent,/kein Standort/);
});

test('printing includes collapsed details and restores their original state',()=>{
  const app=appContext();
  const hours={open:false}, source={open:false}, alreadyOpen={open:true};
  app.getNode('result').querySelectorAll=()=>[hours,source,alreadyOpen];
  app.events.beforeprint();
  assert.ok(hours.open && source.open && alreadyOpen.open);
  app.events.afterprint();
  assert.equal(hours.open,false);assert.equal(source.open,false);assert.equal(alreadyOpen.open,true);
});

test('editing the query discards a delayed response from the previous search',async()=>{
  const app=appContext();
  app.getNode('concern').value='Pass';
  app.run("setLocation(50,8,'Mainz')");
  let resolveResponse;
  app.context.fetch=()=>new Promise(resolve=>{resolveResponse=resolve;});
  const pending=app.run('startSearch()');
  app.run('clearResult()');
  resolveResponse({ok:true,json:async()=>({places:[{ars:'073150000000',name:'Mainz'}]})});
  await pending;
  assert.equal(app.getNode('result-section').hidden,true);
  assert.equal(app.run('lastSearch'),null);
});
