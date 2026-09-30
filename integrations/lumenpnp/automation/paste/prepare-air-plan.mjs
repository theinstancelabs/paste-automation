#!/usr/bin/env node
// Offline only. Imports the pinned fork's pure planner, never its serial runner.
import {readFile, writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash, randomUUID} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import guard from './safety.cjs';
export const COMMIT = 'c497bfbef2f7347538966c129bf7ac7bdc2c1a0f';
export const sha256 = text => createHash('sha256').update(text).digest('hex');
export async function prepare(job, profile, fork) {
  fork = resolve(fork);
  const head = execFileSync('git', ['-C',fork,'rev-parse','HEAD'], {encoding:'utf8'}).trim();
  if (head !== COMMIT) throw Error('Paste fork is not at pinned commit '+COMMIT);
  const source = await readFile(resolve(fork,'automation/planner.js'));
  const pinned = execFileSync('git',['-C',fork,'show',COMMIT+':automation/planner.js']);
  if (!source.equals(pinned)) throw Error('Pure planner differs from pinned commit');
  guard.profile(profile);
  if (job.coordinateFrame !== 'machine') throw Error('Only measured OpenPnP N2 machine coordinates are accepted; transfer board registration explicitly');
  const {planJob} = await import(pathToFileURL(resolve(fork,'automation/planner.js')).href);
  const preview = planJob(job, profile, {dryRun:true});
  const plan = {schema:1, id:randomUUID(), createdAt:new Date().toISOString(), mode:'air',
    coordinateFrame:'openpnp-N2-mm', provenance:{forkCommit:COMMIT,plannerSha256:sha256(source)},
    job, profile, points:job.placements.map(({x,y})=>({x,y})),
    previewOnlyGcode:preview.commands, summary:preview.summary,
    execution:'Native XY only from already verified joint clearance; preview G-code is never executed'};
  guard.plan(plan);
  return plan;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [jobFile, profileFile, output, ...extra] = process.argv.slice(2);
    if (!jobFile || !profileFile || !output || extra.length) throw Error('Usage: node prepare-air-plan.mjs measured-job.json measured-profile.json output.json');
    const fork = resolve(dirname(fileURLToPath(import.meta.url)), '../../../paste-automation');
    const plan = await prepare(JSON.parse(await readFile(jobFile,'utf8')),JSON.parse(await readFile(profileFile,'utf8')),fork);
    const body=JSON.stringify(plan,null,2)+'\n';
    await writeFile(output, body, {flag:'wx'});
    console.log(JSON.stringify({output,sha256:sha256(body),...plan.summary,physicalValidation:false},null,2));
  } catch(e) { console.error(e.message); process.exitCode=1; }
}
