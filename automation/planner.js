/** Pure preflight and G-code planning. This module never opens a machine connection. */
const finite = (value, label) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} must be a finite number`);
    return value;
};
const positive = (value, label) => {
    finite(value, label);
    if (value <= 0) throw new Error(`${label} must be positive`);
    return value;
};
const inside = (value, min, max, label) => {
    finite(value, label);
    if (value < min || value > max) throw new Error(`${label} is outside machine bounds`);
    return value;
};
// Decimal notation avoids firmware-dependent scientific-notation parsing.
const number = value => {
    const text = value.toString();
    if (!/[eE]/.test(text)) return text;
    const [mantissa, exponentText] = text.toLowerCase().split('e');
    const sign = mantissa.startsWith('-') ? '-' : '';
    const unsigned = mantissa.replace('-', '');
    const digits = unsigned.replace('.', '');
    const decimal = (unsigned.indexOf('.') < 0 ? unsigned.length : unsigned.indexOf('.')) + Number(exponentText);
    if (decimal <= 0) return `${sign}0.${'0'.repeat(-decimal)}${digits}`;
    if (decimal >= digits.length) return sign + digits + '0'.repeat(decimal - digits.length);
    return `${sign}${digits.slice(0, decimal)}.${digits.slice(decimal)}`;
};

export function planJob(job, profile, {dryRun = true} = {}) {
    if (!job || typeof job !== 'object' || !profile || typeof profile !== 'object') throw new Error('job and profile are required');
    if (typeof dryRun !== 'boolean') throw new Error('dryRun must be boolean');
    if (profile.calibrated !== true) throw new Error('profile must be calibrated');
    if (!['board', 'machine'].includes(job.coordinateFrame)) throw new Error('coordinateFrame must be board or machine');
    for (const field of ['preGcode', 'postGcode']) {
        if (job[field] !== undefined && (typeof job[field] !== 'string' || job[field].trim())) throw new Error(`${field} must be empty`);
    }
    for (const axis of ['x', 'y', 'z']) {
        finite(profile[`${axis}Min`], `${axis}Min`);
        finite(profile[`${axis}Max`], `${axis}Max`);
        if (profile[`${axis}Min`] >= profile[`${axis}Max`]) throw new Error(`${axis} bounds must be increasing`);
    }
    const safeZ = inside(profile.safeZ, profile.zMin, profile.zMax, 'safeZ');
    if (!['decreasing', 'increasing'].includes(profile.clearanceDirection)) throw new Error('clearanceDirection must be decreasing or increasing');
    for (const feed of ['travelFeed', 'zFeed', 'dispenseFeed']) positive(profile[feed], feed);
    const dose = positive(job.dispenseDegrees, 'dispenseDegrees');
    const retract = finite(job.retractionDegrees, 'retractionDegrees');
    const dwell = finite(job.dwellMilliseconds, 'dwellMilliseconds');
    if (retract < 0 || retract > dose) throw new Error('retractionDegrees must be between zero and dispenseDegrees');
    if (dwell < 0) throw new Error('dwellMilliseconds must be nonnegative');
    if (job.invertDispense !== undefined && typeof job.invertDispense !== 'boolean') throw new Error('invertDispense must be boolean');
    if (!Array.isArray(job.placements) || !job.placements.length) throw new Error('placements must be a nonempty array');
    let tipX = 0, tipY = 0;
    if (job.coordinateFrame === 'board') {
        tipX = finite(profile.tipXoffset, 'tipXoffset');
        tipY = finite(profile.tipYoffset, 'tipYoffset');
    }
    const points = job.placements.map((point, index) => {
        if (!point || typeof point !== 'object') throw new Error(`placement ${index} must be an object`);
        const keyX = job.coordinateFrame === 'board' ? 'calX' : 'x';
        const keyY = job.coordinateFrame === 'board' ? 'calY' : 'y';
        const x = inside(finite(point[keyX], `placement ${index} ${keyX}`) + tipX, profile.xMin, profile.xMax, `placement ${index} X`);
        const y = inside(finite(point[keyY], `placement ${index} ${keyY}`) + tipY, profile.yMin, profile.yMax, `placement ${index} Y`);
        const z = inside(point.z, profile.zMin, profile.zMax, `placement ${index} Z`);
        const clearance = profile.clearanceDirection === 'decreasing' ? z - safeZ : safeZ - z;
        if (clearance <= 0) throw new Error(`safeZ must have clearance from placement ${index}`);
        return {x, y, z};
    });
    const totalDispenseDegrees = finite(dose * points.length, 'total dispense');
    const netDispenseDegrees = finite((dose - retract) * points.length, 'net dispense');
    const commands = ['G21', 'G90'];
    const lift = `G1 Z${number(safeZ)} F${number(profile.zFeed)}`;
    commands.push(lift, 'M400');
    if (!dryRun) commands.push('G92 B0');
    let currentB = 0;
    const direction = job.invertDispense ? 1 : -1;
    for (const {x, y, z} of points) {
        commands.push(`G1 X${number(x)} Y${number(y)} F${number(profile.travelFeed)}`);
        if (dryRun) commands.push('M400');
        if (!dryRun) {
            const dispenseB = finite(currentB + direction * dose, 'B target');
            currentB = finite(dispenseB - direction * retract, 'B retraction target');
            commands.push(`G1 Z${number(z)} F${number(profile.zFeed)}`,
                `G1 B${number(dispenseB)} F${number(profile.dispenseFeed)}`);
            if (retract > 0) commands.push(`G1 B${number(currentB)} F${number(profile.dispenseFeed)}`);
            commands.push(`G4 P${number(dwell)}`, lift, 'M400');
        }
    }
    commands.push(lift, 'M400');
    return {commands, summary: {pointCount: points.length, dryRun, coordinateFrame: job.coordinateFrame,
        safeZ, totalDispenseDegrees: dryRun ? 0 : totalDispenseDegrees, netDispenseDegrees: dryRun ? 0 : netDispenseDegrees}};
}
