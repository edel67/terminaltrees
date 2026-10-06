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

"""Check geometry and the README render. Requires Python 3, pdflatex and Poppler."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
image_mode = parser.add_mutually_exclusive_group()
image_mode.add_argument('--update-readme-image', action='store_true',
                    help='replace the README image after all rendering checks pass')
image_mode.add_argument('--preview', action='store_true',
                       help='validate generated previews without comparing or changing the committed SVG')
args = parser.parse_args()

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(tempfile.mkdtemp(prefix='terminaltrees-check-'))
print('Output directory:', BUILD, flush=True)
ENV = dict(os.environ, max_print_line='1000')


def run(*args):
    return subprocess.run(args, cwd=ROOT, env=ENV, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def normalize_svg_size(data):
    """Make Cairo's PDF-point dimensions explicit without rewriting its drawing."""
    root_end = data.index(b'>', data.index(b'<svg ')) + 1
    header, count = re.subn(
        rb'(\s(?:width|height)="\d+(?:\.\d+)?)(?:pt)?"', rb'\1pt"', data[:root_end])
    assert count == 2, 'Expected Cairo SVG width and height in points or without units'
    return header + data[root_end:]


def layout(log):
    """Check unscaled label boxes, branch segments and rounded-corner envelopes."""
    groups = log.split('TREE: ')[1:]
    assert groups, 'Missing layout trace'
    pitches = []
    for group in groups:
        pitch = float(group.split('pt')[0])
        roundness = float(re.search(r'ROUNDNESS: ([^\n]+)', group)[1])
        arrow_inset = float(re.search(r'ARROW INSET: ([^\n]+)pt', group)[1])
        pitches.append(pitch)
        nodes = [[float(v.replace('pt', '')) for v in line.split(',')]
                 for line in re.findall(r'BOX: ([^\n]+)', group)]
        parents = {}
        leaf_indices = {}

        def subtree(index, parent=None):
            if parent is not None:
                parents[index] = parent
            following = index + 1
            leaves = []
            for _ in range(int(nodes[index][6])):
                following, descendants = subtree(following, index)
                leaves.extend(descendants)
            leaves = leaves or [index]
            leaf_indices[index] = leaves
            return following, leaves

        end, leaves = subtree(0)
        assert end == len(nodes)
        assert max(nodes[i][1] for i in leaves)-min(nodes[i][1] for i in leaves) < .002
        for a, b in zip(leaves, leaves[1:]):
            assert abs(nodes[b][0]-nodes[a][0]-pitch) < .002
        for i, a in enumerate(nodes):
            descendants = leaf_indices[i]
            children = [child for child, parent in parents.items() if parent == i]
            if children:
                midpoint = (nodes[children[0]][0]+nodes[children[-1]][0])/2
                assert abs(a[0]-midpoint) < .002, 'Parent is off its branch midpoint'
            left = nodes[descendants[0]][0]-pitch/2
            right = nodes[descendants[-1]][0]+pitch/2
            padding = a[9]/2
            assert a[0]+a[2]-padding >= left-.002, 'Label escapes left columns'
            assert a[0]+a[3]+padding <= right+.002, 'Label escapes right columns'
            for b in nodes[i+1:]:
                x = min(a[0]+a[3], b[0]+b[3])-max(a[0]+a[2], b[0]+b[2])
                y = min(a[1]+a[5], b[1]+b[5])-max(a[1]+a[4], b[1]+b[4])
                assert x <= .002 or y <= .002, 'Label collision'
        for child, parent in parents.items():
            c, p = nodes[child], nodes[parent]
            start = (p[0], p[1]+p[4])
            end = (c[0], c[1]+c[5])
            siblings = [i for i, ancestor in parents.items() if ancestor == parent]
            clearance = min(start[1]-nodes[i][1]-nodes[i][5] for i in siblings)
            assert c[7] > 0 and abs(c[7]-clearance/2) < .002
            side_runs = [abs(nodes[i][0]-p[0]) for i in siblings if nodes[i][0] != p[0]]
            radius = min([max(0, min(roundness*c[7], c[7]-arrow_inset)),
                          *(run/2 for run in side_runs)]) if c[0] != p[0] else 0
            assert abs(c[8]-radius) < .002
            fork_y = start[1]-c[7]
            points = [start, (p[0], fork_y), (c[0], fork_y), end]
            for a, b in zip(points, points[1:]):
                for n in nodes:
                    left, right = n[0]+n[2]+.002, n[0]+n[3]-.002
                    bottom, top = n[1]+n[4]+.002, n[1]+n[5]-.002
                    if a[0] == b[0]:
                        assert not (left < a[0] < right and
                            min(max(a[1], b[1]), top) > max(min(a[1], b[1]), bottom)), 'Vertical edge collision'
                    else:
                        assert not (bottom < a[1] < top and
                            min(max(a[0], b[0]), right) > max(min(a[0], b[0]), left)), 'Horizontal edge collision'
            # Labels must clear both the departure and arrival bends.
            direction = 1 if c[0] > p[0] else -1
            for x1, x2, y1, y2 in (
                (p[0], p[0]+direction*radius, fork_y, fork_y+radius),
                (c[0]-direction*radius, c[0], fork_y-radius, fork_y),
            ):
                for n in nodes:
                    x = min(max(x1, x2), n[0]+n[3])-max(min(x1, x2), n[0]+n[2])
                    y = min(y2, n[1]+n[5])-max(y1, n[1]+n[4])
                    assert x <= .002 or y <= .002, 'Rounded edge envelope collision'
    return pitches


def curves(pdf, log):
    """Check rendered edge paths in a single-page fixture."""
    svg = pdf.with_suffix('.svg')
    result = run('pdftocairo', '-svg', str(pdf), str(svg))
    assert result.returncode == 0, result.stdout
    paths = [p for p in ET.parse(svg).iter('{http://www.w3.org/2000/svg}path')
             if p.get('fill') == 'none' and p.get('stroke')]
    radii = [(float(row.split(',')[8].replace('pt', '')),
              float(re.search(r'ROUNDNESS: ([^\n]+)', group)[1]))
             for group in log.split('TREE: ')[1:]
             for row in re.findall(r'BOX: ([^\n]+)', group)[1:]]
    assert len(paths) == len(radii), 'Expected one drawn path per child'
    departures = {}
    for path, (radius, roundness) in zip(paths, radii):
        data = path.get('d')
        assert data.count('C') == (2 if radius else 0), 'Missing or extra rounded bend'
        points = list(map(float, re.findall(r'-?\d*\.?\d+(?:e[+-]?\d+)?', data)))
        assert all(a >= b-.01 for a, b in zip(points[1::2], points[3::2])), (
            'Drawn edge doubles back toward its parent')
        if not radius:
            if roundness:
                assert max(points[::2])-min(points[::2]) < .01, 'Aligned branch is not vertical'
        else:
            # Sibling branches on the same side must share their departure curve.
            first_curve = re.search(r'\bC\s+([^MLCZ]+)', data)
            curve_end = list(map(float, first_curve[1].split()))[-2:]
            key = (path.get('transform'), *points[:2], curve_end[0] > points[0])
            departure = data[:first_curve.end()]
            assert departure == departures.setdefault(key, departure), 'Diverging sibling curves'
    print('drawn curves PASS (two bends, shared departures, straight aligned edges)')


def compile_case(name, error=None, directory='terminaltrees-tests'):
    source = ROOT/directory/f'{name}.tex'
    # The page-margin overlay needs a second pass to resolve page anchors.
    for _ in range(2 if name == 'fitting-comparison' else 1):
        result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
                     '-halt-on-error', f'-output-directory={BUILD}', str(source))
        if result.returncode:
            break
    log = (BUILD/f'{name}.log').read_text()
    if error:
        assert result.returncode != 0 and error in log, (name, log[-2000:])
        print(name, 'PASS (expected rejection)')
        return
    assert result.returncode == 0 and 'Overfull' not in log, (name, log[-2000:])
    fits = [[float(v.replace('pt', '')) for v in row.split(';')]
            for row in re.findall(r'FIT: ([^\n]+)', log)]
    assert fits, 'Missing fit trace'
    for scale, font, width, height, available, usable_height, floor, _, _ in fits:
        assert 0 < scale <= 1 and scale*font >= floor-.001
        assert width <= available+.002 and height <= usable_height+.002, (
            name, width, available, height, usable_height)
    pitches = layout(log)
    info = run('pdfinfo', str(BUILD/f'{name}.pdf')).stdout
    media = re.search(r'Page size:\s+([\d.]+) x ([\d.]+) pts', info)
    assert media, info
    for actual, expected in zip(map(float, media.groups()), fits[0][-2:]):
        if name != 'fitting-comparison':
            assert abs(actual-expected*72/72.27) < .01, info
    text = run('pdftotext', str(BUILD/f'{name}.pdf'), '-').stdout
    if name == 'fitting-comparison':
        assert len(fits) == 1 and .8 < fits[0][0] < 1
        raw_width = float(re.search(r'UNFITTED WIDTH: ([\d.]+)pt', log)[1])
        assert raw_width > fits[0][4]
        assert abs(raw_width*fits[0][0]-fits[0][2]) < .002
        available = list(map(float, re.findall(r'UNFITTED AVAILABLE: ([\d.]+)pt', log)))
        raw_widths = list(map(float, re.findall(r'UNFITTED WIDTH: ([\d.]+)pt', log)))
        assert len(raw_widths) == 2 and abs(raw_widths[0]-raw_widths[1]) < .002
        assert available[0] > raw_width > available[1]
        assert len(pitches) == 3 and max(pitches)-min(pitches) < .002
        sizes = run('pdfinfo', '-f', '1', '-l', '3', str(BUILD/f'{name}.pdf')).stdout
        dimensions = re.findall(r'Page\s+\d+ size:\s+([\d.]+) x ([\d.]+) pts', sizes)
        assert len(dimensions) == 3, sizes
        areas = re.findall(r'PAGE AREA: ([^\n]+)', log)
        assert len(areas) == 3
        for area in areas:
            paper, left, width = [float(v.replace('pt', '')) for v in area.split(';')]
            assert abs(left-35*72.27/25.4) < .002
            assert abs(paper-left-width-left) < .002
        for (width, height), paper_width in zip(dimensions, (220, 170, 170)):
            assert abs(float(width)-paper_width*72/25.4) < .01
            assert abs(float(height)-140*72/25.4) < .01
        pages = text.split('\f')
        assert len(pages) == 4 and not pages[-1].strip()
        assert 'Unfitted' in pages[0] and 'Fitted' in pages[1]
        assert 'When the page is too small' in pages[2]
    elif name == 'fit':
        assert fits[0][0] == fits[2][0] == 1 and .8 < fits[1][0] < 1
        pages = text.split('\f')
        assert 'stays on the first page' in pages[0]
        assert 'follows the tree on the next page' in pages[1]
    elif name == 'height':
        assert .7 < fits[0][0] < 1
    elif name == 'labels':
        assert fits[0][1] == 9 and fits[1][1] == 10
    elif name == 'adaptive':
        assert [fit[6] for fit in fits] == [10, 10, 9.5]
        assert fits[1][1] > fits[0][1] and pitches[1] > pitches[0]
        assert fits[2][1] == fits[0][1] and pitches[2] == pitches[0]
    elif name == 'override':
        assert 7 < fits[0][0]*fits[0][1] < 8 and fits[0][6] == 7
    elif name == 'curves':
        curves(BUILD/f'{name}.pdf', log)
    elif name == 'roundness':
        assert len(fits) == 7 and all(fit == fits[0] for fit in fits)
        groups = log.split('TREE: ')[1:]
        assert [float(re.search(r'ROUNDNESS: ([^\n]+)', group)[1]) for group in groups] == [
            0, .25, .5, .75, 1, 0, 1]
        boxes = [re.findall(r'BOX: ([^\n]+)', group) for group in groups]
        geometry = [[row.split(',')[:8]+row.split(',')[9:] for row in tree] for tree in boxes]
        assert all(tree == geometry[0] for tree in geometry), 'Roundness moved nodes'
        assert boxes[4] == boxes[-1], 'Default roundness changed or leaked between trees'
        assert boxes[0] == boxes[5], 'Square setting leaked between trees'
        curves(BUILD/f'{name}.pdf', log)
    print(name, 'PASS', len(fits), 'trees')


# Cairo versions emit either bare PDF-point dimensions or explicit pt units.
expected_svg = (b'<svg width="12.5pt" height="7pt" viewBox="0 0 12.5 7">'
                b'<rect width="12.5" height="7"/><path d="M0 0 L1 1"/></svg>')
for units in (b'', b'pt'):
    converted_svg = expected_svg.replace(b'pt"', units + b'"')
    assert normalize_svg_size(converted_svg) == expected_svg, 'SVG sizing changed drawing bytes'
try:
    normalize_svg_size(expected_svg.replace(b'pt"', b'px"'))
except AssertionError:
    pass
else:
    raise AssertionError('Unexpected SVG units were accepted')
print('SVG sizing PASS (both converter formats, unchanged drawing, unexpected-unit rejection)')

for name in ('fit', 'height', 'labels', 'adaptive', 'override', 'branches', 'centering', 'curves', 'roundness'):
    compile_case(name)
compile_case('fitting-comparison', directory='examples')

# The overview must preserve the relative sizes of the two verified pages.
overview = ROOT/'examples/fitting-overview.tex'
result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
             '-halt-on-error', f'-output-directory={BUILD}', '-jobname=fitting-overview',
             r'\AtBeginDocument{\graphicspath{{' + str(BUILD) + r'/}}}\input{' + str(overview) + '}')
log = (BUILD/'fitting-overview.log').read_text()
assert result.returncode == 0 and 'Overfull' not in log, log[-2000:]
info = run('pdfinfo', str(BUILD/'fitting-overview.pdf')).stdout
assert re.search(r'Pages:\s+1\b', info), info
label_widths = []
for pdf in ('fitting-comparison', 'fitting-overview'):
    result = run('pdftotext', '-bbox', str(BUILD/f'{pdf}.pdf'), '-')
    assert result.returncode == 0, result.stdout
    words = ET.fromstring(result.stdout).iter('{http://www.w3.org/1999/xhtml}word')
    label_widths.append([float(word.get('xMax'))-float(word.get('xMin'))
                         for word in words if word.text == 'alpha'])
assert list(map(len, label_widths)) == [3, 2], 'Missing comparison labels'
display_scales = [shown/actual for actual, shown in zip(*label_widths)]
assert abs(display_scales[0]-display_scales[1]) < .001, 'Unequal overview display scales'
print('fitting-overview PASS (verified pages, one shared display scale)')
for name, error in (
    ('reject-small', 'the 8.0pt minimum'),
    ('reject-inner', 'requires normal'),
    ('reject-option', 'must be positive'),
    ('reject-font', 'Fitting requires 5pt'),
    ('reject-roundness', 'roundness must be a unitless number'),
):
    compile_case(name, error)

for suffix, value, error in (
    ('above-max', '1.0001', 'roundness must be a unitless number'),
    ('unit', '1pt', 'roundness must be a unitless number'),
    ('text', 'banana', 'Package PGF Math Error'),
    ('nan', 'nan', 'roundness must be a unitless number'),
    ('infinity', 'inf', 'roundness must be a unitless number'),
):
    name = f'reject-roundness-{suffix}'
    result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
                 '-halt-on-error', f'-output-directory={BUILD}', f'-jobname={name}',
                 r'\def\BadRoundness{' + value +
                 r'}\input{terminaltrees-tests/reject-roundness.tex}')
    log = (BUILD/f'{name}.log').read_text()
    assert result.returncode != 0 and error in log, (name, log[-2000:])
    print(name, 'PASS (expected rejection)')

# README snippets without a preamble need a minimal document wrapper.
for i, example in enumerate(re.findall(r'```latex\n(.*?)```',
                                      (ROOT/'README.md').read_text(), re.S)):
    if r'\documentclass' not in example:
        example = (r'\documentclass{article}\usepackage{terminaltrees}'
                   r'\begin{document}' + example + r'\end{document}')
    example = example.replace(r'\begin{document}',
                              r'\input{terminaltrees-tests/trace.tex}\begin{document}')
    source = BUILD/f'guide-{i}.tex'
    source.write_text(example)
    result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
                 '-halt-on-error', f'-output-directory={BUILD}', str(source))
    log = source.with_suffix('.log').read_text()
    assert result.returncode == 0 and 'Overfull' not in log, log[-2000:]
    layout(log)
    print(f'guide-{i} PASS')

# Validate the shared comparison before checking or updating its README image.
example = (ROOT/'examples/comparison.tex').read_text().replace(
    r'\begin{document}', r'\input{terminaltrees-tests/trace.tex}\begin{document}')
source = BUILD/'comparison.tex'
source.write_text(example)
result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
             '-halt-on-error', f'-output-directory={BUILD}', str(source))
log = source.with_suffix('.log').read_text()
assert result.returncode == 0 and 'Overfull' not in log, log[-2000:]
layout(log)
result = run('pdftocairo', '-svg',
             str(source.with_suffix('.pdf')), str(source.with_suffix('.svg')))
assert result.returncode == 0, result.stdout
svg = ET.parse(source.with_suffix('.svg')).getroot()
assert list(svg.iter('{http://www.w3.org/2000/svg}path')), 'Missing vector paths'
assert not list(svg.iter('{http://www.w3.org/2000/svg}image')), 'README image must remain vector'
image = normalize_svg_size(source.with_suffix('.svg').read_bytes())
source.with_suffix('.svg').write_bytes(image)
if args.update_readme_image:
    (ROOT/'examples/comparison.svg').write_bytes(image)
    print('comparison PASS (geometry checked; README image updated)')
elif args.preview:
    print('comparison PASS (geometry checked; preview only)')
else:
    assert image == (ROOT/'examples/comparison.svg').read_bytes(), (
        'README comparison image changed; run python3 terminaltrees-tests/check.py --update-readme-image')
    print('comparison PASS (geometry and exact rendered image)')

for source in (ROOT/'terminaltrees.sty', ROOT/'README.md'):
    print(hashlib.sha256(source.read_bytes()).hexdigest(), source.name)
