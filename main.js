import './style.css';
import { modalManager } from './modal.js';
import { toastManager } from './toast.js';
import { serialManager } from './serialManager.js';
import { Job } from './job.js';
import { Lumen } from './lumen.js';
import { attachAutomation } from './automation/ui.js';

const el = id => document.getElementById(id);
const serial = new serialManager(new modalManager());
const job = new Job(new Lumen(serial), new toastManager());
attachAutomation(job, serial);
const showError = error => { el('automationStatus').textContent = error.message; };
const handle = (id, fn) => el(id).addEventListener('click', async () => { try { await fn(); } catch(error) { showError(error); } });
const invalidate = () => {
  job.coordinateFrame = null;
  el('coordinateFrame').value = '';
  el('commissioned').checked = false;
};

handle('connect', async () => {
  el('connect').disabled = true;
  try { await serial.connect(); invalidate(); }
  finally { el('connect').disabled = false; el('connect').textContent = serial.fault ? 'Reconnect' : 'Connect / reconnect'; }
});
handle('importJob', () => el('jobFile').click());
el('jobFile').addEventListener('change', async () => {
  try {
    invalidate();
    const result = await job.importFromFile(el('jobFile').files[0]);
    if (!result.success) throw new Error(result.error);
    invalidate(); // Saved calibration does not attest to this session's registration.
  } catch(error) { showError(error); }
});
handle('exportJob', async () => { syncSettings(); await job.saveToFile(); });
for (const [button,input,label] of [['selectPasteGerber','pasteGerberFile','pasteGerberFilename'],['selectMaskGerber','maskGerberFile','maskGerberFilename']]) {
  handle(button, () => el(input).click());
  el(input).addEventListener('change', () => { el(label).textContent = el(input).files[0]?.name ?? ''; invalidate(); });
}
handle('loadGerbers', async () => {
  invalidate();
  if (!el('pasteGerberFile').files[0] || !el('maskGerberFile').files[0]) throw new Error('Select paste and mask Gerbers first');
  await job.loadJobFromGerbers();
  invalidate();
});
function syncSettings() {
  for (const [key,id] of [['dispenseDegrees','jobDispenseDeg'],['retractionDegrees','jobRetractionDeg'],['dwellMilliseconds','jobDwellMs']]) job[key] = Number(el(id).value);
  job.invertDispense = el('jobInvertDispense').checked;
  job.preGcode = el('jobPreGcode').value;
  job.postGcode = el('jobPostGcode').value;
}
for (const id of ['jobDispenseDeg','jobRetractionDeg','jobDwellMs','jobInvertDispense','jobPreGcode','jobPostGcode']) el(id).addEventListener('change', syncSettings);

// The inherited calibration/jog controls contain unmeasured Z and camera scale
// assumptions. Commission with the established machine controller, then transfer
// measured coordinates. No legacy motion handlers are registered in this fork.
const legacyIds = ['getRoughBoardPosition','performFidCal','captureNewPos','process-button','homing-fid-button','nozzleOffsetCal','home-x','home-y','home-z','jog-yp','jog-ym','jog-xp','jog-xm','jog-zp','jog-zm','extrude-btn','retract-btn','ring-lights-on','ring-lights-off','left-air-on','left-air-off','left-vac','disable-steppers','send'];
for (const id of legacyIds) { el(id).disabled = true; el(id).title = 'Use the established controller for measured commissioning'; }
// Dynamically created legacy position buttons must never issue blind Z moves.
document.addEventListener('click', event => {
  if (event.target.closest('.move-btn')) { event.preventDefault(); event.stopImmediatePropagation(); }
}, true);
window.addEventListener('unhandledrejection', event => { showError(event.reason instanceof Error ? event.reason : new Error(String(event.reason))); event.preventDefault(); });
