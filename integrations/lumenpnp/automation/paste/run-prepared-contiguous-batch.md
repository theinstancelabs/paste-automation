# Run an explicitly prepared contiguous batch

From the canonical local checkout:

```sh
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir /absolute/path/to/prepared/native --preview
python3 automation/paste/run-prepared-contiguous-batch.py --prepared-dir /absolute/path/to/prepared/native --execute
```

Choose one mode explicitly. Preview dispatches the existing model-only formatter action. Execute runs the existing native-preview finalizer, installs its exact request, and dispatches once through the existing reviewed OpenPnP owner. It performs no new observation or attestation, never changes request IDs or timestamps, and does not create another controller connection. All native evidence, freshness, accounting and motion guards remain in force. Software completion does not establish acceptable paste deposits.

The CLI resolves the repository from its own location and reads only the named prepared directory; it does not read or update `/tmp/current-*` pointers. Before dispatch, it saves `runner-preview-attempt.json` or `runner-execute-attempt.json` with the request SHA-256 and actual report path, and prints that report path. The fixed plan files are protected against concurrent invocations of this runner by a local nonblocking file lock. Other machine workflows must still be coordinated by the operator.

A rerun with an existing attempt or report only observes that same ID; it never replays the action. Polling allows 300 seconds for the explicit eight-pad scope and 60 seconds otherwise. Timeout, bridge failure, stopped state, or uncertain completion must not be treated as permission to retry motion. Keep the attempt record; inspect the actual report through the existing recovery workflow. Even an interrupted attempt that never reached the bridge is deliberately not retried automatically. A successful observation saves `runner-*-result.json`. Finalizer failures occur before dispatch and retain their detailed error.
