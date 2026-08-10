# Component Object -- `sidebar`

Folder scaffold only. Primary navigation menu. Shared by most pages; the navigation engine drives it -- page objects never do.

A control appearing on two or more pages lives here, not in a page object -- one element, one locator ([Locator Standard §3.4](../../../../docs/ADS/locator_standard.md)). Same rules as page objects: read-only, plain data out, locators from `locators/` with provenance, no code until observed.

**Status:** Hypothesis -- never observed.
