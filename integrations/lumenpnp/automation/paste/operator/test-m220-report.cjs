'use strict';
const assert=require('node:assert/strict');
const P=require('../m220-report.cjs');
for(const percent of [0,5,100,999])assert.equal(P.parse([`FR:${percent}%`,'ok']),percent);
assert.equal(P.parse(['echo: FR: 135%','ok N42']),135);
for(const lines of [[],['ok'],['FR:100%'],['FR:100%','FR:100%','ok'],['FR:100% extra','ok'],['FR:1000%','ok'],['FR:-1%','ok'],['FR:1.5%','ok'],['FR:100%','ok','extra'],['fr:100%','ok']])assert.throws(()=>P.parse(lines));
console.log('Strict read-only M220 FR report parser validates one value and its terminal ACK');
