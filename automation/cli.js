import { readFile, writeFile } from 'node:fs/promises';
import { planJob } from './planner.js';
const [jobFile, profileFile, outputFile, mode] = process.argv.slice(2);
try {
  if (!jobFile || !profileFile || !outputFile || (mode && mode !== '--wet')) throw new Error('Usage: npm run plan -- job.json profile.json output.gcode [--wet]');
  const job = JSON.parse(await readFile(jobFile, 'utf8'));
  const profile = JSON.parse(await readFile(profileFile, 'utf8'));
  const plan = planJob(job, profile, {dryRun:mode !== '--wet'});
  // No serial dependency: this command only creates an offline artifact.
  await writeFile(outputFile, plan.commands.join('\n')+'\n', {flag:'wx'});
  console.log(JSON.stringify(plan.summary, null, 2));
} catch (error) { console.error(error.message); process.exitCode = 1; }
