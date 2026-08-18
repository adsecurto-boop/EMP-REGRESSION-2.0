## 2026-08-18 - Pre-compile Regexes in Validator Loops
**Learning:** Parsing screenshot timestamps occurs frequently during cadence validation. Compiling regular expressions dynamically inside functions like `parse_ui_timestamp` creates unnecessary allocation and CPU overhead on repeated calls.
**Action:** Always pre-compile module-level regex patterns (`re.compile`) when functions will be executed in loops or frequent data-validation pipelines.
