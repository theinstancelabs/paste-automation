'use strict';

function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.keys(value).forEach(function (key) { deepFreeze(value[key]); });
    Object.freeze(value);
  }
  return value;
}

function createReader(fs, crypto) {
  var parsedJson = Object.create(null);
  return function readEvidence(evidence, asJson) {
    if (!evidence || typeof evidence.path !== 'string' || typeof evidence.sha256 !== 'string') {
      throw new Error('Hash-bound evidence path and SHA-256 required');
    }
    var bytes = fs.readFileSync(evidence.path);
    var actual = crypto.createHash('sha256').update(bytes).digest('hex');
    if (actual !== evidence.sha256) throw new Error('Evidence SHA-256 mismatch: ' + evidence.path);
    if (!asJson) return bytes.toString('utf8');
    var canonicalPath = fs.realpathSync(evidence.path);
    var key = canonicalPath + '#' + evidence.sha256;
    if (Object.prototype.hasOwnProperty.call(parsedJson, key)) return parsedJson[key];
    var parsed = deepFreeze(JSON.parse(bytes.toString('utf8')));
    parsedJson[key] = parsed;
    return parsed;
  };
}

module.exports = { createReader: createReader };
