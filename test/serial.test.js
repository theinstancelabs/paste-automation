import test from 'node:test';
import assert from 'node:assert/strict';
import { serialManager } from '../serialManager.js';

function fixture(reply, options = {}) {
    const manager = new serialManager(null, { ackTimeoutMs: 25, maxCommandMs: 100, ...options });
    const writes = [];
    let released = false;
    manager.port = { writable: { getWriter: () => ({
        write: async data => { const command = new TextDecoder().decode(data).trim(); writes.push(command); await reply?.(manager, command); },
        releaseLock: () => { released = true; }
    }) } };
    return { manager, writes, released: () => released };
}

test('immediate ACK inside write is preserved, CRLF and advanced ACK accepted', async () => {
    const { manager, writes, released } = fixture(m => m.receiveLine('ok N10 P15 B3\r'));
    await manager.send(['G90', 'M400']);
    assert.deepEqual(writes, ['G90', 'M400']);
    assert.equal(released(), true);
});

test('missing ACK aborts remaining commands and late ACK cannot unlock fault', async () => {
    const { manager, writes } = fixture();
    await assert.rejects(manager.send(['G90', 'G0 X10']), /Timed out/);
    manager.receiveLine('ok');
    await assert.rejects(manager.send(['M400']), /Timed out/);
    assert.deepEqual(writes, ['G90']);
});

test('unrelated telemetry does not extend timeout', async () => {
    const { manager } = fixture();
    const timer = setInterval(() => manager.receiveLine('T:25'), 5);
    try { await assert.rejects(manager.send(['M400']), /Timed out/); }
    finally { clearInterval(timer); }
});

test('busy responses refresh idle timeout but cannot defeat hard deadline', async () => {
    const { manager, writes } = fixture(undefined, { ackTimeoutMs: 40, maxCommandMs: 80 });
    const timer = setInterval(() => manager.receiveLine('echo:busy: processing'), 5);
    try { await assert.rejects(manager.send(['G28', 'G0 X1']), /deadline exceeded/); }
    finally { clearInterval(timer); }
    assert.deepEqual(writes, ['G28']);
});

test('firmware errors and unsupported resend fail closed', async () => {
    for (const error of ['Error:Printer halted', '!! STOP', 'Resend: 1', 'echo:Unknown command: M999']) {
        const { manager, writes } = fixture(m => { m.receiveLine(error); m.receiveLine('ok'); });
        await assert.rejects(manager.send(['G90', 'G0 X1']), /Firmware rejected/);
        await assert.rejects(manager.send(['M400']), /Firmware rejected/);
        assert.deepEqual(writes, ['G90']);
    }
});

test('concurrent sends reject without interleaving or poisoning active send', async () => {
    const { manager, writes } = fixture();
    const first = manager.send(['G90']);
    await assert.rejects(manager.send(['M400']), /already running/);
    manager.receiveLine('ok');
    await first;
    assert.deepEqual(writes, ['G90']);
    assert.equal(manager.fault, null);
});

test('fragmented UTF-8 and CRLF input reconstructed; stream EOF faults session', async () => {
    const { manager } = fixture();
    let controller;
    manager.port.readable = new ReadableStream({ start(c) { controller = c; } });
    const listening = manager.listen();
    const pending = manager.send(['M400']);
    const encoded = new TextEncoder().encode('echo:µ\r\nok\r\n');
    for (const byte of encoded) controller.enqueue(Uint8Array.of(byte));
    await pending;
    assert.deepEqual(manager.inspectBuffer, ['echo:µ', 'ok']);
    controller.close();
    await listening;
    await assert.rejects(manager.send(['M400']), /disconnected/);
});

test('reader failure aborts an active batch promptly', async () => {
    const { manager, writes } = fixture();
    let controller;
    manager.port.readable = new ReadableStream({ start(c) { controller = c; } });
    const listening = manager.listen();
    const pending = manager.send(['G90', 'G0 X1']);
    controller.error(new Error('USB unplugged'));
    await assert.rejects(pending, /USB unplugged/);
    await listening;
    assert.deepEqual(writes, ['G90']);
});

test('stalled write is bounded even if ACK arrived', async () => {
    const { manager } = fixture(m => { m.receiveLine('ok'); return new Promise(() => {}); }, { maxCommandMs: 30 });
    await assert.rejects(manager.send(['G90']), /deadline exceeded/);
});

test('malformed batches are rejected before any write', async () => {
    const { manager, writes } = fixture();
    for (const commands of ['G90', ['G90\nG0 X1'], [''], [null]]) {
        await assert.rejects(manager.send(commands), /single-line/);
    }
    assert.deepEqual(writes, []);
    assert.equal(manager.fault, null);
});

test('disconnect after ACK also aborts stalled write', async () => {
    const { manager } = fixture(m => { m.receiveLine('ok'); return new Promise(() => {}); });
    const pending = manager.send(['G90']);
    manager.fail(new Error('Serial device disconnected'));
    await assert.rejects(pending, /disconnected/);
});

test('a fresh connection resets a fault and finishes initialization before ready', async () => {
    const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    const oldDocument = globalThis.document;
    const { manager, writes } = fixture(m => m.receiveLine('ok'));
    const port = manager.port;
    let controller;
    port.open = async () => {};
    port.close = async () => {};
    port.readable = new ReadableStream({ start(c) { controller = c; } });
    manager.port = undefined;
    manager.fail(new Error('previous fault'));
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { serial: {
        requestPort: async () => port, addEventListener() {}, removeEventListener() {}
    } } });
    globalThis.document = { querySelector: () => null };
    try {
        assert.equal(await manager.connect(), true);
        assert.equal(manager.fault, null);
        assert.equal(writes.length, manager.bootCommands.length);
        assert.deepEqual(writes, ['M115', 'M114']);
        controller.close();
        await manager.listenTask;
    } finally {
        if (oldNavigator) Object.defineProperty(globalThis, 'navigator', oldNavigator);
        else delete globalThis.navigator;
        globalThis.document = oldDocument;
    }
});


test('firmware reset banner aborts batch and late ACK cannot allow more motion', async () => {
    for (const firstReply of ['start', 'ok']) {
        const { manager, writes } = fixture(m => {
            m.receiveLine(firstReply);
            m.receiveLine('start');
            m.receiveLine('ok');
        });
        await assert.rejects(manager.send(['G90', 'G0 X10']), /Firmware restarted/);
        await assert.rejects(manager.send(['G0 X20']), /Firmware restarted/);
        assert.deepEqual(writes, ['G90']);
    }
});

test('firmware reset while idle prevents starting a batch', async () => {
    const { manager, writes } = fixture();
    manager.receiveLine('start\r');
    await assert.rejects(manager.send(['G90']), /Firmware restarted/);
    assert.deepEqual(writes, []);
});
