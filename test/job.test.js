import test from 'node:test';
import assert from 'node:assert/strict';
import { Job } from '../job.js';

function fixture() {
    const listeners = new Set();
    const canvas = { width: 100, height: 100, addEventListener: (_, fn) => listeners.add(fn), removeEventListener: (_, fn) => listeners.delete(fn) };
    const files = {};
    globalThis.document = { getElementById: id => id === 'pointViz' ? canvas : files[id] ?? null };
    const job = new Job({}, { show: async () => false });
    job.drawJobToCanvas = () => {};
    job.loadJobIntoPositionList = () => {};
    return { job, listeners, files };
}
function gerber(body, format = 'LAX24Y24', units = 'MM') {
    return `%FS${format}*%\n%MO${units}*%\n%ADD10C,1*%\nD10*\n${body}\nM02*`;
}
function file(text) { return { files: [{ text: async () => text }] }; }

test('Gerber modal coordinates include preceding moves and convert mm', async () => {
    const { job, files } = fixture();
    files.pasteGerberFile = file(gerber('X10000Y20000D02*\nX30000D03*\nY40000D03*'));
    assert.deepEqual(await job.parseGerber('pasteGerberFile'), [{ x: 3, y: 2 }, { x: 3, y: 4 }]);
});

test('Gerber trailing zeros, sign, and inches convert correctly', async () => {
    const { job, files } = fixture();
    files.pasteGerberFile = file(gerber('X-01Y02D03*', 'TAX24Y24', 'IN'));
    assert.deepEqual(await job.parseGerber('pasteGerberFile'), [{ x: -25.4, y: 50.8 }]);
});

test('Gerber missing files, modal references, incremental, and paste paths fail closed', async () => {
    const { job, files } = fixture();
    await assert.rejects(job.parseGerber('pasteGerberFile'), /Select/);
    for (const text of [gerber('X10000D03*'), gerber('X1Y1D03*', 'LIX24Y24'), gerber('X0Y0D02*\nX10000Y10000D01*')]) {
        files.pasteGerberFile = file(text);
        await assert.rejects(job.parseGerber('pasteGerberFile'));
    }
});

function importFixture() {
    const f = fixture();
    f.job.parseGerber = async id => id === 'pasteGerberFile' ? [{ x: 1, y: 1 }] : [
        { x: 1.0001, y: 1 }, { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }
    ];
    return f;
}

test('mask subtraction compares coordinates, reload replaces data, listeners removed', async () => {
    const { job, listeners } = importFixture();
    for (let repeat = 0; repeat < 2; repeat++) {
        let index = 0;
        job.toast.show = async () => job.fiducials[index++];
        await job.loadJobFromGerbers();
        assert.equal(job.placements.length, 1);
        assert.equal(job.fiducials.length, 3);
        assert.equal(listeners.size, 0);
    }
});

test('cancel, repeated fiducial, and toast failure always remove listeners', async () => {
    for (const mode of ['cancel', 'duplicate', 'throw']) {
        const { job, listeners } = importFixture();
        job.toast.show = async () => {
            if (mode === 'throw') throw new Error('toast failed');
            return mode === 'cancel' ? false : job.fiducials[0];
        };
        await assert.rejects(job.loadJobFromGerbers());
        assert.equal(listeners.size, 0);
        assert.equal(job.loadingGerbers, false);
    }
});

test('registration maps known points and rejects degenerate/nonfinite triangles atomically', () => {
    const { job } = fixture();
    job.fiducials = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }];
    job.placements = [{ x: 2, y: 3 }];
    job.transformPlacements([[10, 20], [20, 20], [10, 30]]);
    assert.equal(job.placements[0].calX, 12);
    assert.equal(job.placements[0].calY, 23);
    for (const points of [[[0, 0], [0, 0], [1, 1]], [[0, 0], [1, 1], [2, 2]], [[0, 0], [1, 0], [NaN, 1]]]) {
        assert.throws(() => job.transformPlacements(points));
        assert.equal(job.placements[0].calX, 12);
    }
    job.fiducials = [{ x: 0, y: 0 }];
    assert.throws(() => job.transformPlacements([[0, 0], [1, 0], [0, 1]]), /three/);
});

async function importJSON(job, data) {
    globalThis.FileReader = class { readAsText() { this.onload({ target: { result: JSON.stringify(data) } }); } };
    return job.importFromFile({});
}

test('JSON import validates before mutation, preserves zero doses, requires session registration', async () => {
    const { job } = fixture();
    const data = { placements: [{ x: 1, y: 2, z: 3 }], dispenseDegrees: 0, retractionDegrees: 0, dwellMilliseconds: 0, coordinateFrame: 'machine' };
    assert.equal((await importJSON(job, data)).success, true);
    assert.equal(job.dispenseDegrees, 0);
    assert.equal(job.retractionDegrees, 0);
    assert.equal(job.dwellMilliseconds, 0);
    assert.equal(job.coordinateFrame, null);
    for (const invalid of [{ ...data, placements: [{ x: '1', y: 2, z: 3 }] }, { ...data, dispenseDegrees: -1 }, { ...data, tipXoffset: '<script>' }]) {
        assert.equal((await importJSON(job, invalid)).success, false);
        assert.equal(job.placements[0].x, 1);
    }
});

test('bundled KiCad paste and mask Gerbers still import finite flashed positions', async () => {
    const { readFile } = await import('node:fs/promises');
    const { job, files } = fixture();
    for (const [id, name] of [['pasteGerberFile', 'ftp-F_Paste.gbr'], ['maskGerberFile', 'ftp-F_Mask.gbr']]) {
        files[id] = file(await readFile(new URL(name, import.meta.url), 'utf8'));
        const points = await job.parseGerber(id);
        assert.ok(points.length > 0);
        assert.ok(points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y)));
    }
});

test('JSON import preserves externally measured finite calibrated positions', async () => {
    const { job } = fixture();
    const result = await importJSON(job, { placements: [{ x: 1, y: 2, z: 3, calX: 101, calY: 202 }] });
    assert.equal(result.success, true);
    assert.equal(job.placements[0].calX, 101);
    assert.equal(job.placements[0].calY, 202);
    assert.equal(job.coordinateFrame, null);
});
