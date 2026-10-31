# Contributing to terminaltrees

For installation and usage, see the [README](https://github.com/edel67/terminaltrees/blob/main/README.md)
and [user manual](https://mirrors.ctan.org/graphics/pgf/contrib/terminaltrees/terminaltrees-doc.pdf).

## Check and preview

From the checkout or extracted archive, run:

```sh
python3 terminaltrees-tests/check.py --preview
```

The checker needs Python 3, `pdflatex`, `pdfinfo`, `pdftotext`, `pdftocairo`, and
the `standalone` class. It prints the temporary directory containing the PDFs
and SVG. Geometry and rendering checks run without requiring the generated SVG
to match the committed one.

Open `fitting-overview.pdf` for a shared-scale comparison of natural-size and
fitted trees. `fitting-comparison.pdf` contains the actual-size pages and a third
page showing deliberate unfitted overflow. You choose the paper in both cases.
The example uses `leaf pitch=16mm`, not the default. Use the same zoom on each
actual-size page to preserve the comparison.

Without `--preview`, the checker also requires a byte-for-byte match with the
README SVG. To replace that image after all checks pass, run:

```sh
python3 terminaltrees-tests/check.py --update-readme-image
```

Different TeX, font or Poppler versions can change the SVG without changing the
layout. Review the rendering before accepting an image update.

### GitHub previews and the README image

PR checks upload validated renderings as `tree-previews-…` artifacts, retained
for 14 days. They never commit or push. New revisions cancel only that PR's
older run.

The [image workflow](https://github.com/edel67/terminaltrees/blob/main/.github/workflows/readme-image.yml) rebuilds the vector
comparison after pushes to `main`, runs the checks, and commits only if the
image changed. Failed checks leave the previous image in place. The
[example source](https://github.com/edel67/terminaltrees/blob/main/examples/comparison.tex)
defines one tree shared by both sides of the comparison.

## Build the manual and distribution archive

Run the checker first, then build with Python 3 and the TeX dependencies:

```sh
python3 terminaltrees-tests/check.py --preview
python3 build-ctan.py /path/to/new-output-directory
```

The output directory must not exist. The builder creates `terminaltrees-doc.pdf`
and `terminaltrees.zip`. The ZIP contains the files listed in
[manifest.txt](https://github.com/edel67/terminaltrees/blob/main/manifest.txt) under `terminaltrees/`.

## Versioning

Version numbers follow [Semantic Versioning](https://semver.org/) for the
documented environments and options. Incompatible interface changes require a
new major version.

Before publishing, give the Unreleased changelog entry its version and release
date. Keep the GitHub release notes consistent with that entry.

