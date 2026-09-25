import { planJob } from './planner.js';
import { JobRunner } from './runner.js';

export function attachAutomation(job, serial) {
  const el = id => document.getElementById(id);
  let profile = null, reviewed = null, record = null;
  const status = text => { el('automationStatus').textContent = text; };
  const input = () => {
    const data = JSON.parse(job.export());
    data.coordinateFrame = el('coordinateFrame').value;
    // Read visible settings even while the optional vision runtime is loading.
    for (const [key, id] of [['dispenseDegrees','jobDispenseDeg'],['retractionDegrees','jobRetractionDeg'],['dwellMilliseconds','jobDwellMs']]) data[key] = Number(el(id).value);
    data.invertDispense = el('jobInvertDispense').checked;
    data.preGcode = el('jobPreGcode').value;
    data.postGcode = el('jobPostGcode').value;
    return { job: data, profile, options: { dryRun: el('dryRun').checked } };
  };
  const download = (name, text) => {
    const url = URL.createObjectURL(new Blob([text], {type:'text/plain'}));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const guarded = fn => async () => { try { await fn(); } catch (error) { status(error.message); } };
  const runner = new JobRunner(lines => serial.send(lines), ({state,completed}) => status(`${state}: ${completed} commands acknowledged`));
  const prepare = () => { const data = input(); return { data, key: JSON.stringify(data), plan: planJob(data.job, data.profile, data.options) }; };
  el('machineProfile').addEventListener('change', guarded(async () => {
    profile = null; reviewed = null;
    profile = JSON.parse(await el('machineProfile').files[0].text());
    el('profileStatus').textContent = `Loaded ${el('machineProfile').files[0].name}. Preview validates the profile.`;
    el('commissioned').checked = false;
  }));
  el('coordinateFrame').addEventListener('change', () => { job.coordinateFrame = el('coordinateFrame').value; });
  el('previewPlan').addEventListener('click', guarded(() => {
    reviewed = null;
    reviewed = prepare();
    el('planPreview').textContent = reviewed.plan.commands.join('\n');
    status(JSON.stringify(reviewed.plan.summary, null, 2));
  }));
  el('downloadPlan').addEventListener('click', guarded(() => {
    const current = prepare();
    if (!reviewed || current.key !== reviewed.key) throw new Error('Preview the current job and settings first');
    download('paste-plan.gcode', current.plan.commands.join('\n')+'\n');
  }));
  el('runJob').addEventListener('click', guarded(async () => {
    if (!el('commissioned').checked) throw new Error('Complete the session checks before motion');
    const current = prepare();
    if (!reviewed || current.key !== reviewed.key) throw new Error('Job or settings changed: preview again');
    if (!serial.port?.writable) throw new Error('Connect the machine first');
    const allowed = new Set(['pausePlan','resumePlan','cancelPlan']);
    const controls = [...document.querySelectorAll('button,input,select,textarea')].map(node => [node,node.disabled]);
    controls.forEach(([node]) => { if (!allowed.has(node.id)) node.disabled = true; });
    // Also block canvas-based jogging and keyboard shortcuts during a job.
    const block = event => { if (!allowed.has(event.target.id)) { event.preventDefault(); event.stopImmediatePropagation(); } };
    document.addEventListener('click', block, true);
    document.addEventListener('keydown', block, true);
    record = { startedAt: new Date().toISOString(), input: current.data, plan: current.plan };
    reviewed = null; // Every repeat requires a fresh review.
    try { await runner.run(current.plan.commands); }
    catch (error) { record.error = error.message; throw error; }
    finally {
      record.finishedAt = new Date().toISOString(); record.state = runner.state; record.events = [...runner.events];
      controls.forEach(([node,disabled]) => { node.disabled = disabled; });
      document.removeEventListener('click', block, true); document.removeEventListener('keydown', block, true);
      el('commissioned').checked = false;
    }
  }));
  el('pausePlan').addEventListener('click', () => runner.pause());
  el('resumePlan').addEventListener('click', () => runner.resume());
  el('cancelPlan').addEventListener('click', () => runner.cancel());
  el('downloadRun').addEventListener('click', guarded(() => {
    if (!record) throw new Error('No run record yet');
    download('paste-run.json', JSON.stringify(record, null, 2));
  }));
}
