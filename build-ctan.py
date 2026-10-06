# Copyright 2026 Adi Edelhaus
#
# terminaltrees is licensed under the LaTeX Project Public
# License, version 1.3c or any later version.
#
# Maintenance status: maintained
# Current maintainer: Adi Edelhaus
# Issue reports: https://github.com/edel67/terminaltrees/issues
#
# The files comprising this work are listed in manifest.txt.
# See LICENSE for the full license terms.

"""Build the manual and CTAN ZIP in a new output directory. Requires pdfLaTeX."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    raise SystemExit('Usage: python3 build-ctan.py NEW_OUTPUT_DIRECTORY')
output = Path(sys.argv[1]).resolve()
if output.exists():
    raise SystemExit(f'Output directory already exists: {output}')

# The manifest is the single file list for both source and generated outputs.
manifest = (ROOT / 'manifest.txt').read_text(encoding='utf-8')
source_section, generated_section = manifest.split('Generated files:\n', 1)
sources = [line.strip() for line in source_section.splitlines() if line.startswith('  ')]
generated = [line.strip() for line in generated_section.splitlines() if line.startswith('  ')]

with tempfile.TemporaryDirectory(prefix='terminaltrees-ctan-') as temporary:
    stage = Path(temporary) / 'terminaltrees'
    build = Path(temporary) / 'build'
    build.mkdir()
    for name in sources:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    # Retain the checked-in vector image; the existing checker verifies it.
    shutil.copyfile(ROOT / 'examples/comparison.svg', stage / 'examples/comparison.svg')
    env = dict(os.environ, TEXINPUTS=f'{stage}//{os.pathsep}{build}//{os.pathsep}')
    for name in ('examples/fitting-comparison.tex', 'examples/fitting-overview.tex',
                 'terminaltrees-doc.tex'):
        for _ in range(3):
            result = subprocess.run(
                ['pdflatex', '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                 f'-output-directory={build}', name], cwd=stage, env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode:
                raise SystemExit(result.stdout)
        shutil.copyfile(build / (Path(name).stem + '.pdf'), stage / (Path(name).stem + '.pdf'))
    # Only manifest entries enter the ZIP, never TeX intermediates or Git data.
    output.mkdir(parents=True)
    with zipfile.ZipFile(output / 'terminaltrees.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sources + generated:
            archive.write(stage / name, f'terminaltrees/{name}')
    shutil.copyfile(stage / 'terminaltrees-doc.pdf', output / 'terminaltrees-doc.pdf')
print(f'Manual: {output / "terminaltrees-doc.pdf"}')
print(f'Archive: {output / "terminaltrees.zip"}')
