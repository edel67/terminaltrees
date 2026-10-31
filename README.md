# terminaltrees

Evenly spaced leaves. Rounded branches. Ordinary Forest syntax.

![The same expression tree in default Forest (left) and terminaltrees (right). terminaltrees aligns x, +, y, *, and 2 at equal intervals on one baseline and rounds the side branches.](https://raw.githubusercontent.com/edel67/terminaltrees/main/examples/comparison.svg)

[Zoom the vector comparison](https://raw.githubusercontent.com/edel67/terminaltrees/main/examples/comparison.svg).
Both trees use the same content and 10pt type, without scaling.

Add `terminal tree` to a [Forest](https://ctan.org/pkg/forest) tree to align its
leaves, center each parent between its first and last immediate children, and
draw rounded branches. Wider labels increase spacing automatically. Children
directly below their parent connect straight down.

## Install and draw a tree

**TeX Live:**

```sh
tlmgr install terminaltrees
```

If your operating system manages TeX Live, use its package manager instead.

**MiKTeX:** refresh the package catalogue, then install:

```sh
miktex packages update-package-database
miktex packages install terminaltrees
```

**Manual installation or Overleaf:** download the
[CTAN archive](https://mirrors.ctan.org/graphics/pgf/contrib/terminaltrees.zip)
and place `terminaltrees.sty` beside your document. Your TeX installation also
needs Forest and `needspace`.

Compile this example with pdfLaTeX:

```latex
\documentclass{article}
\usepackage{terminaltrees}

\begin{document}
\begin{forest}
  terminal tree
  [EXPR
    [EXPR [ID [x]]]
    [+]
    [EXPR [EXPR [ID [y]]] [*] [EXPR [NUM [2]]]]
  ]
\end{forest}
\end{document}
```

This produces the right-hand tree. Remove `terminal tree` for Forest's default
layout on the left. Labels use ordinary LaTeX, including `\\` for line breaks.

## Keep the type size, or fit the page

Both forms use Forest and the same layout:

- **Natural size:** use `forest` with `terminal tree`. You choose paper large
  enough for the tree and manage its placement, including in figures or minipages.
- **Fit to the existing layout:** use `fittedterminaltree` in ordinary
  single-column document flow. It shrinks the whole tree when needed and moves
  it to the next page if the remaining space is insufficient.

```latex
\begin{fittedterminaltree}
  [EXPR [EXPR [x]] [+] [EXPR [1]]]
\end{fittedterminaltree}
```

`fittedterminaltree` applies `terminal tree` automatically. It scales labels and
branches together, with a minimum label size based on the current `\footnotesize`.
Compilation stops if that limit cannot be met. Neither form changes paper or
margins, enlarges trees, or splits them across pages. Fitting does not support
floats, minipages, or multicolumn layouts.

See the [manual](https://mirrors.ctan.org/graphics/pgf/contrib/terminaltrees/terminaltrees-doc.pdf)
for fitting comparisons, font-size settings, and measurement limits. The
font-size floor is not a readability guarantee.

## Adjust the layout

Put these options after `terminal tree`, or before the root bracket in
`fittedterminaltree`:

| Option | Default | Effect |
| --- | --- | --- |
| `leaf pitch` | `0pt` | Minimum distance between leaf centers. Zero uses label measurements and Forest's padding alone. |
| `roundness` | `1` | From square corners (`0`) to the largest bends that fit (`1`). Does not move nodes or change fitting. |

For example, `terminal tree, leaf pitch=3em, roundness=0.5` sets a minimum leaf
spacing and tighter bends. Both options reset for each tree. Forest's font,
label, arrow and vertical-spacing options remain available.

Equal leaf spacing does not imply equal internal sibling spacing. Custom
anchors, shifted labels, overlays and arrow styles need visual inspection.
The package does not add tagged-PDF tree semantics or screen-reader support.

## Documentation and support

- [Changelog](https://github.com/edel67/terminaltrees/blob/main/CHANGELOG.md): changes by release.
- [User manual](https://mirrors.ctan.org/graphics/pgf/contrib/terminaltrees/terminaltrees-doc.pdf): examples, fitting, geometry, and compatibility limits.
- [Contributor guide](https://github.com/edel67/terminaltrees/blob/main/CONTRIBUTING.md): checks, previews, and release builds.
- [Report an issue](https://github.com/edel67/terminaltrees/issues).

## License and credits

Copyright 2026 Adi Edelhaus. Licensed under the [LaTeX Project Public License,
version 1.3c or later](https://github.com/edel67/terminaltrees/blob/main/LICENSE).
Maintenance status: maintained. Current maintainer: Adi Edelhaus.
The work's files are listed in [manifest.txt](https://github.com/edel67/terminaltrees/blob/main/manifest.txt).

Built on [Forest](https://ctan.org/pkg/forest) by Sašo Živanović,
[PGF/TikZ](https://ctan.org/pkg/pgf), the [LaTeX kernel](https://www.latex-project.org/)
and [needspace](https://ctan.org/pkg/needspace). These dependencies retain their
own licenses and are not bundled.
