# Pre-declared service objective

Declared 2026-11-06 before running the load tests in this repository.

Target: p95 <= 60 seconds from accepted submission until a terminal result is observable,
at 3 concurrent clients with one worker and a 1.5-second fixed delay per stub completion.
Also require >= 95% of accepted cases to finish with verified recommendations in the
synthetic supported-case workload. Escalations caused by exhausted deadlines count as
failed useful work, not as a successful low-latency answer.

An officer can tolerate a short investigative wait, but a queue that routinely takes over
a minute obstructs interactive grievance handling. The hard end-to-end deadline is 90
seconds including queue wait. The objective is an engineering choice, not a utility SLA.

Repeat at increasing concurrency until the target fails. Measure terminal-result RPS,
not submission RPS. Compare one and three workers with cache disabled, then compare
cache off/on with a repeated workload. Keep the provider stub delay unchanged. Record
machine, image versions, worker count, delay, concurrency and cache setting in every result.
Do not change this target after observing measurements.
