import test from 'node:test';
import assert from 'node:assert/strict';
import { JobRunner } from '../automation/runner.js';

test('cancel drains current point only, without blind recovery moves', async () => {
  const sent = [];
  const runner = new JobRunner(async ([line]) => { sent.push(line); if (line === 'G1 B-30') runner.cancel(); });
  await runner.run(['G1 B-30', 'G1 Z10', 'M400', 'G1 X100', 'M400']);
  assert.deepEqual(sent, ['G1 B-30', 'G1 Z10', 'M400']);
  assert.equal(runner.state, 'cancelled');
});
test('serial fault stops immediately and propagates', async () => {
  const sent = [];
  const runner = new JobRunner(async ([line]) => { sent.push(line); throw new Error('ACK timeout'); });
  await assert.rejects(runner.run(['G21', 'M400']), /ACK timeout/);
  assert.deepEqual(sent, ['G21']);
  assert.equal(runner.state, 'faulted');
});
test('pause stops only at completed motion boundary and resumes', async () => {
  const sent = [];
  let paused;
  const reachedPause = new Promise(resolve => { paused = resolve; });
  const runner = new JobRunner(async ([line]) => { sent.push(line); if (line === 'G21') runner.pause(); }, ({state}) => { if (state === 'paused') paused(); });
  const running = runner.run(['G21', 'M400', 'G90', 'M400']);
  await reachedPause;
  assert.deepEqual(sent, ['G21', 'M400']);
  await assert.rejects(runner.run(['M400']), /already active/);
  runner.resume();
  await running;
  assert.equal(runner.state, 'completed');
});
