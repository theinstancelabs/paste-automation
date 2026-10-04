'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');const src=fs.readFileSync(require.resolve('../../scripts/Paste_Experiment_Console.js'),'utf8');
const recipe=src.slice(src.indexOf('        function recipe(){'),src.indexOf('        function update(){'));
let checked=false;const c={busy:false,fields:{doseDegrees:{commitEdit:()=>{},getValue:()=>30}},heightMode:{getSelectedItem:()=> 'gap'},retractEachPad:{isSelected:()=>checked}};vm.createContext(c);vm.runInContext(recipe,c);assert.equal(c.recipe().retractEachPad,false);checked=true;assert.equal(c.recipe().retractEachPad,true);
assert(src.includes("'Retract after each pad',retained.retractEachPad===true"));assert(src.includes('retained.retractEachPad=component.isSelected()'));assert(src.includes('retractEachPad.setSelected(saved.recipe.retractEachPad===true)'));assert(src.includes('retractEachPad.setEnabled(!busy)'));
console.log('Per-pad UI recipe wiring true/false, reload retention, saved-recipe load and busy lock verified');
