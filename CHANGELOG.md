# Changelog

## Unreleased

- Reject fitted trees whose labels fall below the requested minimum size. Previously, labels could be up to 0.0001pt below the limit. Public options and tree geometry are unchanged.
- Add MiKTeX installation instructions.
- Add a contributor guide for checks, previews, and release builds.
- Include this changelog in the package archive.

## [1.0.1] - 2026-10-09

- Add TeX Live installation instructions and clarify manual installation for MiKTeX and Overleaf.
- Fix README image and file links on CTAN, and replace the unsupported section jump with a plain section reference.

Tree layout, fitting behavior, and public options are unchanged in this release.

## [1.0.0] - 2026-10-06

Initial release.

- Add the `terminal tree` style for evenly spaced leaves on a shared baseline and rounded side branches using Forest syntax. Each parent is centered between its first and last immediate children.
- Provide `leaf pitch` and `roundness` options for spacing and curvature.
- Add `fittedterminaltree` to shrink a whole tree to the existing page layout, subject to a minimum label size. It can move the tree to the next page but does not resize the paper or split trees across pages.

[1.0.1]: https://github.com/edel67/terminaltrees/releases/tag/v1.0.1
[1.0.0]: https://github.com/edel67/terminaltrees/releases/tag/v1.0.0
