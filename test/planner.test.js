import test from 'node:test';
import assert from 'node:assert/strict';
import {planJob} from '../automation/planner.js';
import {JobRunner} from '../automation/runner.js';
const profile = () => ({calibrated: true, xMin: 0, xMax: 100, yMin: 0, yMax: 100, zMin: 0, zMax: 100, safeZ: 10, clearanceDirection: 'decreasing', travelFeed: 500, zFeed: 100, dispenseFeed: 30, tipXoffset: 2, tipYoffset: -3});
const job = () => ({coordinateFrame: 'board', placements: [{x: 1, y: 2, calX: 20, calY: 30, z: 50}], dispenseDegrees: 30, retractionDegrees: 1, dwellMilliseconds: 100, invertDispense: false});

test('default dry run visits transformed XY at clearance without dispensing or surface approach', () => {
    const {commands, summary} = planJob(job(), profile());
    assert.ok(commands.includes('G1 X22 Y27 F500'));
    assert.ok(commands.includes('G1 Z10 F100'));
    assert.ok(!commands.some(c => /\bB|G92|Z50|G4 /.test(c)));
    assert.equal(summary.totalDispenseDegrees, 0);
    assert.deepEqual(commands.slice(-2), ['G1 Z10 F100', 'M400']);
});
test('wet cycle uses cumulative negative B, retract, dwell and clearance between points', () => {
    const j = job(); j.placements.push({...j.placements[0], calX: 40});
    const {commands, summary} = planJob(j, profile(), {dryRun: false});
    assert.deepEqual(commands.filter(c => /\bB/.test(c)), ['G92 B0', 'G1 B-30 F30', 'G1 B-29 F30', 'G1 B-59 F30', 'G1 B-58 F30']);
    assert.equal(commands.filter(c => c === 'G4 P100').length, 2);
    const second = commands.indexOf('G1 X42 Y27 F500');
    assert.deepEqual(commands.slice(second - 2, second), ['G1 Z10 F100', 'M400']);
    assert.equal(summary.netDispenseDegrees, 58);
});
test('inverted dispensing and machine coordinates are explicit', () => {
    const j = job(); j.coordinateFrame = 'machine'; j.invertDispense = true;
    const p = profile(); delete p.tipXoffset; delete p.tipYoffset;
    const {commands} = planJob(j, p, {dryRun: false});
    assert.ok(commands.includes('G1 X1 Y2 F500'));
    assert.ok(commands.includes('G1 B30 F30'));
    assert.ok(commands.includes('G1 B29 F30'));
});
test('increasing clearance and zero retract/dwell are supported', () => {
    const p = profile(); p.safeZ = 90; p.clearanceDirection = 'increasing';
    const j = job(); j.retractionDegrees = 0; j.dwellMilliseconds = 0;
    assert.ok(planJob(j, p, {dryRun: false}).commands.includes('G1 Z90 F100'));
});
test('rejects incomplete calibration, bounds, feeds, coordinates and dangerous raw commands', () => {
    const invalid = [
        (j,p) => p.calibrated = false, (j,p) => delete p.xMin,
        (j,p) => p.xMax = p.xMin, (j,p) => p.safeZ = 101,
        (j,p) => p.safeZ = 50, (j,p) => p.safeZ = 60,
        (j,p) => p.clearanceDirection = 'up', (j,p) => p.travelFeed = '500',
        (j,p) => p.zFeed = 0, (j,p) => p.dispenseFeed = NaN,
        (j,p) => p.tipXoffset = Infinity, (j,p) => p.tipXoffset = 100,
        j => delete j.coordinateFrame, j => j.placements = [],
        j => delete j.placements[0].calY, j => j.placements[0].calX = '20',
        j => j.placements[0].z = null, j => j.placements[0].z = 101,
        j => j.dispenseDegrees = 0, j => j.retractionDegrees = 31,
        j => j.retractionDegrees = -1, j => j.dwellMilliseconds = -1,
        j => j.invertDispense = 'false', j => j.preGcode = 'G0 X900',
        j => j.postGcode = 'G92', j => j.postGcode = [],
        j => j.placements.push({...j.placements[0], calX: 200})
    ];
    for (const mutate of invalid) {
        const j = job(), p = profile(); mutate(j,p);
        assert.throws(() => planJob(j,p), undefined, String(mutate));
    }
});
test('planning does not mutate job/profile and all point validation applies to dry runs', () => {
    const j = job(), p = profile(), before = JSON.stringify({j,p});
    planJob(j,p); assert.equal(JSON.stringify({j,p}), before);
    j.placements.push({...j.placements[0], z: NaN});
    assert.throws(() => planJob(j,p), /finite/);
    assert.throws(() => planJob(job(),p,{dryRun: 'false'}), /boolean/);
});


test('wet planner boundaries permit cancel only after retraction, dwell and safe lift', async () => {
    const j = job(); j.placements.push({...j.placements[0], calX: 40});
    const {commands} = planJob(j, profile(), {dryRun: false});
    for (let i = 0; i < commands.length; i++) {
        if (commands[i] === 'M400') assert.equal(commands[i - 1], 'G1 Z10 F100');
    }
    const sent = [];
    const runner = new JobRunner(async ([line]) => {
        sent.push(line);
        if (line === 'G1 B-30 F30') runner.cancel();
    });
    await runner.run(commands);
    assert.equal(runner.state, 'cancelled');
    assert.deepEqual(sent.slice(-5), ['G1 B-30 F30', 'G1 B-29 F30', 'G4 P100', 'G1 Z10 F100', 'M400']);
    assert.ok(!sent.includes('G1 X42 Y27 F500'));
});
