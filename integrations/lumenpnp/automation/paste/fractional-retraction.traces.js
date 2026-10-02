var FractionalRetractionTraces = (function () {
    var C = CommissioningStroke;
    var percentages = [15, 20, 25, 30];
    var settings = percentages.map(function (p) {
        return C.retractionCountsForPercent(p, 6, 4.44);
    });
    var groups = percentages.map(function (p, i) {
        var ids = [];
        for (var n = 0; n < 8; n++) ids.push('G' + (i + 1) + 'P' + (n + 1));
        return { group: i + 1, retractPercent: p, padIds: ids };
    });
    var record = { schema: 1, protocol: 'four-group-fractional-retraction-comparison',
        doseDegrees: 6, stepsPerDegree: 4.44, groups: groups };
    var stages = percentages.map(function (p, i) {
        var spec = settings[i];
        var stage = { axis: 'B', startRaw: { B: 100 }, targetRaw: { B: 100 + spec.requestedDegrees } };
        var delta = stage.targetRaw.B - stage.startRaw.B;
        var countDelta = C.controllerStepCount(stage.targetRaw.B) - C.controllerStepCount(stage.startRaw.B);
        var pad = { padId: groups[i].padIds[0], group: i + 1, retractPercent: p,
            actualRetractRawDelta: delta, actualRetractControllerSteps: countDelta,
            actualQuantizedRetractionDegrees: countDelta / 4.44 };
        return C.validateFractionalRetractionComparison(record, pad, stage, 4.44);
    });
    var phaseTarget = { axis: 'B', startRaw: { B: -240 }, targetRaw: { B: -238.86 } };
    var phaseDelta = phaseTarget.targetRaw.B - phaseTarget.startRaw.B;
    var phaseCountDelta = C.controllerStepCount(phaseTarget.targetRaw.B) - C.controllerStepCount(phaseTarget.startRaw.B);
    var phasePad = { padId: groups[1].padIds[0], group: 2, retractPercent: 20,
        actualRetractRawDelta: phaseDelta, actualRetractControllerSteps: phaseCountDelta,
        actualQuantizedRetractionDegrees: phaseCountDelta / 4.44 };
    var phaseFit = C.validateFractionalRetractionComparison(record, phasePad,
        phaseTarget, 4.44);
    var rejected = 0;
    try { C.validateFractionalRetractionComparison({ schema: 1, protocol: record.protocol,
        doseDegrees: 6, stepsPerDegree: 4.44,
        groups: groups.map(function (g) { return { group: g.group, retractPercent: g.retractPercent, padIds: g.padIds.slice(0) }; })
            .map(function (g, i) { if (i === 0) g.retractPercent = 20; return g; }) }); }
    catch (e) { rejected++; }
    var last = { batchId: '12345678-1234-1234-1234-123456789abc', stageIndex: 0,
        startB: 100, targetB: 100.9, deltaDegrees: 0.9, absoluteDegrees: 0.9,
        batchScope: 'contiguous-native-ftp-retraction-comparison',
        retractionComparisonGroup: 1, retractionPercent: 15, controllerStepDelta: 4, status: 'reserved' };
    var q = { id: last.batchId, previewStages: [{ axis: 'B' }] };
    var ledger = { status: 'reserved', activeBatchId: q.id, lastVerifiedB: 100, entries: [last] };
    C.markBatchStep(ledger, q, 0, 100.91);
    var badLedgerRejected = false;
    try { C.markBatchStep(ledger, q, 0, 101.1); } catch (e2) { badLedgerRejected = true; }
    return { settings: settings, stageSteps: stages.map(function (x) { return x.actualCountDelta; }),
        phaseDependentCount: phaseFit.actualCountDelta,
        malformedComparisonRejected: rejected === 1, ledgerCountMismatchRejected: badLedgerRejected };
}());
