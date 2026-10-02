'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const L=require('./contiguous-linear-counts.cjs');
const counts=(x,y=0,z=0)=>({X:x,Y:y,Z:z,A:200,B:-3526});
const stage=(axis,start,target)=>({axis,startRaw:{[axis]:start},targetRaw:{[axis]:target}});

test('accepts X stage delta across nonzero post-home count origin',()=>{
 const result=L.compare(counts(99066),counts(101667),stage('X',309.49,317.62));
 assert.ok(Math.abs(result.expectedSignedDelta-2601.6)<1e-9);assert.equal(result.observedSignedDelta,2601);
});
test('accepts signed reversals with bounded one-step rounding',()=>{
 assert.equal(L.compare(counts(101667),counts(99066),stage('X',317.62,309.49)).observedSignedDelta,-2601);
 assert.equal(L.compare(counts(4800,6400,1000),counts(4800,6400,800),stage('Z',25,20)).expectedSignedDelta,-200);
});
test('rejects wrong direction and true count mismatch',()=>{
 assert.throws(()=>L.compare(counts(99066),counts(96465),stage('X',309.49,317.62)),/delta mismatch/);
 assert.throws(()=>L.compare(counts(99066),counts(101665),stage('X',309.49,317.62)),/delta mismatch/);
});
test('keeps every nonmoving axis count exact',()=>{
 assert.throws(()=>L.compare(counts(99066),{...counts(101667),Y:1},stage('X',309.49,317.62)),/Other controller axis count changed/);
});
test('rejects noninteger counts and invalid linear scale inputs',()=>{
 assert.throws(()=>L.compare({...counts(1),X:1.5},counts(2),stage('X',0,1)),/safe integer/);
 assert.throws(()=>L.compare(counts(1),counts(2),stage('A',0,1)),/axis must be X, Y or Z/);
});
