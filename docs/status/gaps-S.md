# gaps-S

## Done
- Reviewed all five screenshots (overview, attacks, zk, overheads, limitations) against their named sources; wrote docs/screenshot_review.md; appended UI-G-S-1..6 to docs/ui_issues.md.
- Receipt ids on the ZK page recomputed with hashlib (sha256[:12]) and match.

## Blocked
- Nothing blocked. No Playwright, servers or builds were run.

## Needs
- Fix UI-G-S-3 and UI-G-S-5 (medium). The rest are cosmetic.
- Screenshots are single-theme (light page, sidebar dark); dark variants (overview-dark, attacks-dark) were out of scope. The header button reads "Light theme" in all shots; it is unclear whether that labels the current or the target theme.
- The overheads and limitations images were viewed in crops; text was legible. Cell-level pixel contrast was judged by eye, not measured.
