// Cooperative controls take effect only after an acknowledged M400 boundary.
// They do not interrupt motion already accepted by the controller.
export class JobRunner {
  constructor(send, onState = () => {}) {
    this.send = send;
    this.onState = onState;
    this.state = 'idle';
    this.pauseRequested = false;
    this.cancelRequested = false;
    this.events = [];
  }
  transition(state, completed) {
    this.state = state;
    this.events.push({ state, completed, at: new Date().toISOString() });
    this.onState({ state, completed });
  }
  pause() { if (this.state === 'running') this.pauseRequested = true; }
  resume() { this.pauseRequested = false; this.wake?.(); }
  cancel() { this.cancelRequested = true; this.resume(); }
  async run(commands) {
    if (['running', 'paused'].includes(this.state)) throw new Error('A job is already active');
    if (!Array.isArray(commands) || commands.at(-1) !== 'M400') throw new Error('Plan must end at a motion boundary');
    const snapshot = [...commands];
    this.pauseRequested = false;
    this.cancelRequested = false;
    this.events = [];
    this.transition('running', 0);
    let completed = 0;
    try {
      for (const command of snapshot) {
        await this.send([command]);
        completed++;
        if (command !== 'M400') continue;
        if (this.cancelRequested) { this.transition('cancelled', completed); return; }
        if (this.pauseRequested) {
          this.transition('paused', completed);
          await new Promise(resolve => { this.wake = resolve; });
          this.wake = null;
          if (this.cancelRequested) { this.transition('cancelled', completed); return; }
          this.transition('running', completed);
        }
      }
      this.transition('completed', completed);
    } catch (error) {
      this.transition('faulted', completed);
      throw error;
    }
  }
}
