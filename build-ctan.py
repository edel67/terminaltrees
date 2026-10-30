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
# Allow cross-references in the manual and examples to settle.
LATEX_PASSES = 3


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 build-ctan.py NEW_OUTPUT_DIRECTORY')
    output_dir = Path(sys.argv[1]).resolve()
    if output_dir.exists():
        raise SystemExit(f'Output directory already exists: {output_dir}')

    # The manifest is the single file list for both source and generated outputs.
    manifest = (ROOT / 'manifest.txt').read_text(encoding='utf-8')
    source_section, generated_section = manifest.split('Generated files:\n', 1)
    source_files = [line.strip() for line in source_section.splitlines() if line.startswith('  ')]
    generated_files = [line.strip() for line in generated_section.splitlines() if line.startswith('  ')]

    with tempfile.TemporaryDirectory(prefix='terminaltrees-ctan-') as temporary:
        staging_dir = Path(temporary) / 'terminaltrees'
        build_dir = Path(temporary) / 'build'
        build_dir.mkdir()
        for relative_path in source_files:
            target = staging_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative_path, target)
        # Image generation belongs to terminaltrees-tests/check.py.
        shutil.copyfile(ROOT / 'examples/comparison.svg', staging_dir / 'examples/comparison.svg')
        environment = dict(os.environ, TEXINPUTS=f'{staging_dir}//{os.pathsep}{build_dir}//{os.pathsep}')
        for source in ('examples/fitting-comparison.tex', 'examples/fitting-overview.tex',
                       'terminaltrees-doc.tex'):
            for _ in range(LATEX_PASSES):
                result = subprocess.run(
                    ['pdflatex', '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                     f'-output-directory={build_dir}', source], cwd=staging_dir, env=environment,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise SystemExit(result.stdout)
            pdf_name = Path(source).with_suffix('.pdf').name
            shutil.copyfile(build_dir / pdf_name, staging_dir / pdf_name)
        # Only manifest entries enter the ZIP, never TeX intermediates or Git data.
        output_dir.mkdir(parents=True)
        with zipfile.ZipFile(output_dir / 'terminaltrees.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for relative_path in source_files + generated_files:
                archive.write(staging_dir / relative_path, f'terminaltrees/{relative_path}')
        shutil.copyfile(staging_dir / 'terminaltrees-doc.pdf', output_dir / 'terminaltrees-doc.pdf')
    print(f'Manual: {output_dir / "terminaltrees-doc.pdf"}')
    print(f'Archive: {output_dir / "terminaltrees.zip"}')


if __name__ == '__main__':
    main()
