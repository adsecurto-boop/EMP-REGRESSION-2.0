# Locator Standard

## 1. Purpose

The single official policy for how dashboard elements are located, waited on, retried, and maintained. It binds every locator committed to `framework/dashboard/locators/` and every refactoring of recorded scripts.

**Standing caveat:** the dashboard has never been observed, so **zero locators exist today and none may be invented**. This standard governs how locators will be *recorded from observation*, not a list of locators.

## 2. Priority Order

When recording a locator for an observed element, use the highest tier the page actually supports:

| Tier | Form | Use when |
|---|---|---|
| 1 | `data-testid` → `page.get_by_test_id(...)` | The dashboard renders test ids. Do not assume it does — verify on first observation |
| 2 | `id` → `page.locator("#...")` | The id is semantic and stable (not framework-generated noise like `ember-1234` / `:r5:` — a generated id is *lower* priority than role) |
| 3 | Role → `page.get_by_role(role, name=...)` | Element has an accessible role and stable accessible name |
| 4 | `aria-label` → `page.get_by_label(...)` | Labelled form controls and icon buttons |
| 5 | Stable CSS | Short (≤3 combinators), anchored on semantic classes or attributes; **forbidden**: positional selectors (`nth-child`, `nth-of-type`), style-utility classes (`.mt-2`, `.col-md-6`), generated class hashes |
| 6 | XPath | Last resort, requires a justification comment naming why tiers 1–5 failed. Text-anchored XPath is language-fragile — record the observed locale alongside it |

Text-based locators (`get_by_text`) sit between 4 and 5: acceptable for uniquely-worded controls, but every text locator is a localisation liability — the `localization` page register entry exists precisely because display language is configurable.

## 3. Locator Registry Rules

1. **Central, per page.** All locators for a page live in that page's module under `framework/dashboard/locators/` as named constants. Page objects reference the registry; an inline selector string inside a page object or navigation method is a review-blocking defect.
2. **Named for meaning, not mechanics.** `SCREENSHOT_GRID`, not `DIV_CLASS_GALLERY_WRAPPER`.
3. **Provenance is mandatory.** Every locator records, adjacent to the constant: observed date, dashboard version observed against, source recording (from the [Recording Plan](../design/Playwright_Recording_Plan.md)), and tier. A locator without provenance is treated as invented and removed. This is the locator-level application of the six-field rule in [knowledge_base README §6.1](../../knowledge_base/README.md).
4. **One element, one locator.** Duplicates across page modules mean the element is a shared component — move it to the component's registry.
5. **Broken ≠ patched silently.** When a locator stops resolving, the fix is re-observation and a provenance update — the same demote-rather-than-repair discipline the knowledge base applies on version change.

## 4. Waiting Strategy

1. **Playwright auto-waiting is the first mechanism.** Actions and `expect()` assertions wait for actionability; do not wrap them in manual polls.
2. **Explicit waits are condition-based**: `expect(locator).to_be_visible()`, `wait_for_url`, `wait_for_load_state` — with timeouts from `dashboard.timeouts`, never literals.
3. **`time.sleep()` is forbidden** in the dashboard layer. A fixed sleep either wastes the timeout budget or hides a race; both corrupt timing-sensitive evidence (`observed_at` must mean "when this was actually read").
4. **Readiness is per-page and observed, not assumed.** Each page object defines a readiness condition (its anchor element visible). Until a page has been observed, its readiness condition is a TODO in the page README — not a guess.
5. **Empty is a state, not a wait failure.** Page specs require distinguishing empty-state from error from not-loaded; a wait that times out on the data grid must then check the empty-state indicator before reporting the page unreadable.

## 5. Retry Strategy

1. Retries use `framework.shared.utils.retry.RetryPolicy` (bounded attempts, backoff) — the framework's one retry mechanism.
2. **Retry unit = one read operation** (navigate-and-read a page, read a value set), never a whole collection cycle, and never through authentication.
3. **Only infrastructure failures are retryable**: navigation timeout, transient network error, crashed page. A *successful read of an unwelcome value* (missing element, empty list, `reached=False`) is an observation — retrying it until it improves would fabricate evidence.
4. Every retry attempt is logged with its reason; the attempt count travels in the observation's metadata so a flaky page is visible in evidence rather than smoothed over.

## 6. Stale Element Handling

Playwright locators are re-resolved on every action, so Selenium-style `StaleElementReferenceException` does not exist. The equivalent failure modes and their handling:

| Failure | Meaning | Handling |
|---|---|---|
| Element detached during action | Page re-rendered mid-read | The action auto-retries internally; if the operation-level timeout is hit, treat as a transient infrastructure failure (§5.3, retryable once) |
| Strict-mode violation (locator resolves to >1 node) | The locator is under-specified — a locator defect, not a runtime accident | Fail the read, report it, fix the locator with re-observation. Never "pick the first" with `.first` as a workaround; `.first` is only acceptable where the page spec itself says "a list of N, read the first" |
| Locator resolves to 0 nodes after readiness | Element absent | An observation (`values` absent / element missing), not an error — feeds `PresenceValidator` |
| **Never** hold and re-use an `ElementHandle` across navigations | Handles do go stale | Page objects use `Locator` API exclusively; `ElementHandle` is forbidden in the dashboard layer |

## 7. Interaction Whitelist

Because locators exist to *read*, the interactions a locator may be used for are: navigation clicks on register-listed paths, filter/date-range input, paging, and reading text/attributes/states. Any other interaction — anything on the write list in [Dashboard Automation Standard §3.1](dashboard_automation_standard.md) — may not appear against any locator in this framework.

## 8. Cross References

- [Dashboard Automation Standard](dashboard_automation_standard.md) — parent policy
- [Dashboard Page Specifications](../design/Dashboard_Page_Specifications.md) — the elements these locators will bind to, once observed
- [Recording Plan](../design/Playwright_Recording_Plan.md) — where locator provenance originates
- [Coding Standards](coding_standards.md) · [Configuration Standard](configuration_standard.md)

---
**Document Status:** Active — policy binding; zero locators recorded (dashboard unobserved)
**Owner:** TODO
**Last Updated:** 2026-07-31
