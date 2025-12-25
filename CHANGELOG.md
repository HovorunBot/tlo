## 0.1.0 (2025-12-25)

### Feat

- integrate ScheduleProtocol in test scheduler, improve docs, and add pre-commit hooks
- introduce nested settings loader
- add stop_task interface
- implement task locking
- add logging support to the application
- drop support of python 3.10 and 3.11 to simplify application support
- implement in-memory MVP of task runner
- implement Queue objets to store defined task to run
- implement TaskStateStore, tlo context and simple settings
- implement abstract task registry and generalize interfaces
- implement simple task registry

### Fix

- introduce improvements to Queue interfaces
- commit missing orchestrator files
- resolve pytest run
- mistakes in github CI runners
- mistakes in github CI runners

### Refactor

- remove in-house cron utilities, migrate to hv-utils cron parser
