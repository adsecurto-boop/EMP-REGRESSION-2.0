## 2026-08-22 - [Memoize Log Parsing and Filtering in App.tsx]
**Learning:** In React applications that handle raw log streams (e.g. `log.txt` contents in state), running inline string splits (`logs.split('\n')`) and regex matching (`line.match(...)`) inside the component render body (or inline IIFE) executes on every single component state change (keypresses, toast timeouts, timer ticks).
**Action:** Extract log line parsing regex outside component scope and wrap raw log parsing in `useMemo([logs])` and log filtering in `useMemo([parsedLogs, categoryFilter, searchTerm])`.
