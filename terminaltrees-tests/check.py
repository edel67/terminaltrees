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
from typing import NamedTuple
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
# Keep each TeX trace record on one log line.
ENV = dict(os.environ, max_print_line='1000')
LOG_TAIL_LENGTH = 2000

# Allow accumulated TeX/PGF arithmetic error and rounded geometry traces.
GEOMETRY_TOLERANCE_PT = .002
# Allow rounding in font traces. The precision cases check exact thresholds.
FONT_TRACE_TOLERANCE_PT = .001
# Cairo path coordinates and pdfinfo page sizes have separate rounding budgets.
PATH_TOLERANCE_BP = .01
PAGE_SIZE_TOLERANCE_BP = .01
# Compare the reduction factors inferred from preview text widths.
DISPLAY_SCALE_TOLERANCE = .001

# An inch contains 72.27 TeX points (pt) or 72 PDF points (bp).
TEX_PT_TO_BP = 72 / 72.27
TEX_PT_PER_MM = 72.27 / 25.4
BP_PER_MM = TEX_PT_PER_MM * TEX_PT_TO_BP


def run(*command):
    return subprocess.run(command, cwd=ROOT, env=ENV, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def normalize_svg_size(svg_bytes):
    """Make Cairo's PDF-point dimensions explicit without rewriting its drawing."""
    root_end = svg_bytes.index(b'>', svg_bytes.index(b'<svg ')) + 1
    header, count = re.subn(
        rb'(\s(?:width|height)="\d+(?:\.\d+)?)(?:pt)?"', rb'\1pt"', svg_bytes[:root_end])
    assert count == 2, 'Expected Cairo SVG width and height in points or without units'
    return header + svg_bytes[root_end:]


class NodeTrace(NamedTuple):
    """Fields emitted by BOX in trace.tex, with lengths in TeX points."""

    x: float
    y: float
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    child_count: int
    fork_distance: float
    edge_radius: float
    sibling_gap: float

    @property
    def left(self):
        return self.x + self.min_x

    @property
    def right(self):
        return self.x + self.max_x

    @property
    def bottom(self):
        return self.y + self.min_y

    @property
    def top(self):
        return self.y + self.max_y


class FitTrace(NamedTuple):
    """Fields emitted by FIT in trace.tex, with lengths in TeX points."""

    scale: float
    smallest_font: float
    width: float
    height: float
    available_width: float
    available_height: float
    minimum_font: float
    paper_width: float
    paper_height: float


def parse_nodes(tree_log):
    nodes = []
    for row in re.findall(r'BOX: ([^\n]+)', tree_log):
        node = NodeTrace(*(float(value.replace('pt', '')) for value in row.split(',')))
        nodes.append(node._replace(child_count=int(node.child_count)))
    return nodes


def check_layout(log):
    """Check unscaled label boxes, branch segments and rounded-corner envelopes."""
    trees = log.split('TREE: ')[1:]
    assert trees, 'Missing layout trace'
    pitches = []
    for tree_log in trees:
        pitch = float(tree_log.split('pt')[0])
        roundness = float(re.search(r'ROUNDNESS: ([^\n]+)', tree_log)[1])
        arrow_inset = float(re.search(r'ARROW INSET: ([^\n]+)pt', tree_log)[1])
        pitches.append(pitch)
        nodes = parse_nodes(tree_log)
        parents = {}
        leaf_indices = {}

        def collect_subtree(index, parent=None):
            # BOX records follow Forest's preorder traversal.
            if parent is not None:
                parents[index] = parent
            next_index = index + 1
            leaves = []
            for _ in range(nodes[index].child_count):
                next_index, descendants = collect_subtree(next_index, index)
                leaves.extend(descendants)
            leaves = leaves or [index]
            leaf_indices[index] = leaves
            return next_index, leaves

        next_index, leaves = collect_subtree(0)
        assert next_index == len(nodes)
        leaf_heights = [nodes[index].y for index in leaves]
        assert max(leaf_heights) - min(leaf_heights) < GEOMETRY_TOLERANCE_PT
        for left_index, right_index in zip(leaves, leaves[1:]):
            spacing = nodes[right_index].x - nodes[left_index].x
            assert abs(spacing - pitch) < GEOMETRY_TOLERANCE_PT
        for index, node in enumerate(nodes):
            descendants = leaf_indices[index]
            children = [child for child, parent in parents.items() if parent == index]
            if children:
                midpoint = (nodes[children[0]].x + nodes[children[-1]].x) / 2
                assert abs(node.x - midpoint) < GEOMETRY_TOLERANCE_PT, 'Parent is off its branch midpoint'
            left_column = nodes[descendants[0]].x - pitch / 2
            right_column = nodes[descendants[-1]].x + pitch / 2
            padding = node.sibling_gap / 2
            assert node.left - padding >= left_column - GEOMETRY_TOLERANCE_PT, 'Label escapes left columns'
            assert node.right + padding <= right_column + GEOMETRY_TOLERANCE_PT, 'Label escapes right columns'
            for other in nodes[index + 1:]:
                overlap_x = min(node.right, other.right) - max(node.left, other.left)
                overlap_y = min(node.top, other.top) - max(node.bottom, other.bottom)
                assert overlap_x <= GEOMETRY_TOLERANCE_PT or overlap_y <= GEOMETRY_TOLERANCE_PT, (
                    'Label collision')
        for child_index, parent_index in parents.items():
            child, parent = nodes[child_index], nodes[parent_index]
            start = (parent.x, parent.bottom)
            end = (child.x, child.top)
            siblings = [nodes[index] for index, ancestor in parents.items() if ancestor == parent_index]
            clearance = min(parent.bottom - sibling.top for sibling in siblings)
            assert child.fork_distance > 0
            assert abs(child.fork_distance - clearance / 2) < GEOMETRY_TOLERANCE_PT
            side_runs = [abs(sibling.x - parent.x) for sibling in siblings if sibling.x != parent.x]
            radius = 0
            if child.x != parent.x:
                vertical_limit = max(0, min(roundness * child.fork_distance,
                                            child.fork_distance - arrow_inset))
                radius = min(vertical_limit, *(distance / 2 for distance in side_runs))
            assert abs(child.edge_radius - radius) < GEOMETRY_TOLERANCE_PT
            fork_y = parent.bottom - child.fork_distance
            points = [start, (parent.x, fork_y), (child.x, fork_y), end]
            for segment_start, segment_end in zip(points, points[1:]):
                for node in nodes:
                    left = node.left + GEOMETRY_TOLERANCE_PT
                    right = node.right - GEOMETRY_TOLERANCE_PT
                    bottom = node.bottom + GEOMETRY_TOLERANCE_PT
                    top = node.top - GEOMETRY_TOLERANCE_PT
                    start_x, start_y = segment_start
                    end_x, end_y = segment_end
                    if start_x == end_x:
                        overlap_y = min(max(start_y, end_y), top) - max(min(start_y, end_y), bottom)
                        assert not (left < start_x < right and overlap_y > 0), 'Vertical edge collision'
                    else:
                        overlap_x = min(max(start_x, end_x), right) - max(min(start_x, end_x), left)
                        assert not (bottom < start_y < top and overlap_x > 0), 'Horizontal edge collision'
            # Labels must clear both the departure and arrival bends.
            direction = 1 if child.x > parent.x else -1
            for x1, x2, bottom, top in (
                (parent.x, parent.x + direction * radius, fork_y, fork_y + radius),
                (child.x - direction * radius, child.x, fork_y - radius, fork_y),
            ):
                for node in nodes:
                    overlap_x = min(max(x1, x2), node.right) - max(min(x1, x2), node.left)
                    overlap_y = min(top, node.top) - max(bottom, node.bottom)
                    assert overlap_x <= GEOMETRY_TOLERANCE_PT or overlap_y <= GEOMETRY_TOLERANCE_PT, (
                        'Rounded edge envelope collision')
    return pitches


def check_curves(pdf, log):
    """Check rendered edge paths in a single-page fixture."""
    svg = pdf.with_suffix('.svg')
    result = run('pdftocairo', '-svg', str(pdf), str(svg))
    assert result.returncode == 0, result.stdout
    paths = [path for path in ET.parse(svg).iter('{http://www.w3.org/2000/svg}path')
             if path.get('fill') == 'none' and path.get('stroke')]
    radii = [(node.edge_radius, float(re.search(r'ROUNDNESS: ([^\n]+)', tree_log)[1]))
             for tree_log in log.split('TREE: ')[1:]
             for node in parse_nodes(tree_log)[1:]]
    assert len(paths) == len(radii), 'Expected one drawn path per child'
    departures = {}
    for path, (radius, roundness) in zip(paths, radii):
        drawing = path.get('d')
        # Each rounded edge has one departure bend and one arrival bend.
        assert drawing.count('C') == (2 if radius else 0), 'Missing or extra rounded bend'
        coordinates = list(map(float, re.findall(r'-?\d*\.?\d+(?:e[+-]?\d+)?', drawing)))
        x_coordinates = coordinates[::2]
        y_coordinates = coordinates[1::2]
        assert all(start_y >= end_y - PATH_TOLERANCE_BP
                   for start_y, end_y in zip(y_coordinates, y_coordinates[1:])), (
            'Drawn edge doubles back toward its parent')
        if not radius:
            if roundness:
                assert max(x_coordinates) - min(x_coordinates) < PATH_TOLERANCE_BP, (
                    'Aligned branch is not vertical')
        else:
            # Sibling branches on the same side must share their departure curve.
            first_curve = re.search(r'\bC\s+([^MLCZ]+)', drawing)
            curve_end_x, _ = map(float, first_curve[1].split()[-2:])
            departure_key = (path.get('transform'), *coordinates[:2], curve_end_x > x_coordinates[0])
            departure = drawing[:first_curve.end()]
            assert departure == departures.setdefault(departure_key, departure), 'Diverging sibling curves'
    print('drawn curves PASS (two bends, shared departures, straight aligned edges)')


def compile_document(build_dir, name, tex_input, *, passes=1, expected_error=None):
    for _ in range(passes):
        result = run('pdflatex', '-no-shell-escape', '-interaction=batchmode',
                     '-halt-on-error', f'-output-directory={build_dir}', f'-jobname={name}', str(tex_input))
        if result.returncode:
            break
    log = (build_dir / f'{name}.log').read_text()
    if expected_error:
        assert result.returncode != 0 and expected_error in log, (name, log[-LOG_TAIL_LENGTH:])
    else:
        assert result.returncode == 0 and 'Overfull' not in log, (name, log[-LOG_TAIL_LENGTH:])
    return log


def check_fitting_comparison(pdf, log, fits, pitches, text):
    # This fixture should shrink by less than 20% to fit the narrower page.
    assert len(fits) == 1 and .8 < fits[0].scale < 1
    fitted = fits[0]
    natural_widths = list(map(float, re.findall(r'UNFITTED WIDTH: ([\d.]+)pt', log)))
    available_widths = list(map(float, re.findall(r'UNFITTED AVAILABLE: ([\d.]+)pt', log)))
    natural_width = natural_widths[0]
    assert natural_width > fitted.available_width
    assert abs(natural_width * fitted.scale - fitted.width) < GEOMETRY_TOLERANCE_PT
    assert len(natural_widths) == 2
    assert abs(natural_widths[0] - natural_widths[1]) < GEOMETRY_TOLERANCE_PT
    assert available_widths[0] > natural_width > available_widths[1]
    assert len(pitches) == 3 and max(pitches) - min(pitches) < GEOMETRY_TOLERANCE_PT

    # These paper sizes and margins are specified in fitting-comparison.tex.
    paper_widths_mm = (220, 170, 170)
    paper_height_mm = 140
    margin_mm = 35
    page_count = len(paper_widths_mm)
    info = run('pdfinfo', '-f', '1', '-l', str(page_count), str(pdf)).stdout
    dimensions = re.findall(r'Page\s+\d+ size:\s+([\d.]+) x ([\d.]+) pts', info)
    assert len(dimensions) == page_count, info
    page_areas = re.findall(r'PAGE AREA: ([^\n]+)', log)
    assert len(page_areas) == page_count
    for area in page_areas:
        paper_width, left_margin, text_width = [float(value.replace('pt', '')) for value in area.split(';')]
        assert abs(left_margin - margin_mm * TEX_PT_PER_MM) < GEOMETRY_TOLERANCE_PT
        assert abs(paper_width - left_margin - text_width - left_margin) < GEOMETRY_TOLERANCE_PT
    for (width, height), paper_width_mm in zip(dimensions, paper_widths_mm):
        assert abs(float(width) - paper_width_mm * BP_PER_MM) < PAGE_SIZE_TOLERANCE_BP
        assert abs(float(height) - paper_height_mm * BP_PER_MM) < PAGE_SIZE_TOLERANCE_BP
    pages = text.split('\f')
    assert len(pages) == page_count + 1 and not pages[-1].strip()
    assert 'Unfitted' in pages[0] and 'Fitted' in pages[1]
    assert 'When the page is too small' in pages[2]


def check_roundness(pdf, log, fits):
    expected_roundness = [0, .25, .5, .75, 1, 0, 1]
    assert len(fits) == len(expected_roundness) and all(fit == fits[0] for fit in fits)
    trees = log.split('TREE: ')[1:]
    assert [float(re.search(r'ROUNDNESS: ([^\n]+)', tree)[1]) for tree in trees] == expected_roundness
    nodes_by_tree = [parse_nodes(tree) for tree in trees]
    geometry = [[node._replace(edge_radius=0) for node in nodes] for nodes in nodes_by_tree]
    assert all(tree == geometry[0] for tree in geometry), 'Roundness moved nodes'
    # The final two trees repeat square corners and the fully rounded default.
    square, _, _, _, full, repeated_square, default = nodes_by_tree
    assert full == default, 'Default roundness changed or leaked between trees'
    assert square == repeated_square, 'Square setting leaked between trees'
    check_curves(pdf, log)


def check_case(build_dir, name, expected_error=None, directory='terminaltrees-tests'):
    source = ROOT / directory / f'{name}.tex'
    # The page-margin overlay needs a second pass to resolve page anchors.
    log = compile_document(build_dir, name, source,
                           passes=2 if name == 'fitting-comparison' else 1,
                           expected_error=expected_error)
    if expected_error:
        print(name, 'PASS (expected rejection)')
        return
    fits = [FitTrace(*(float(value.replace('pt', '')) for value in row.split(';')))
            for row in re.findall(r'FIT: ([^\n]+)', log)]
    assert fits, 'Missing fit trace'
    for fit in fits:
        assert 0 < fit.scale <= 1
        assert fit.scale * fit.smallest_font >= fit.minimum_font - FONT_TRACE_TOLERANCE_PT
        assert (fit.width <= fit.available_width + GEOMETRY_TOLERANCE_PT and
                fit.height <= fit.available_height + GEOMETRY_TOLERANCE_PT), (name, fit)
    pitches = check_layout(log)
    pdf = build_dir / f'{name}.pdf'
    info = run('pdfinfo', str(pdf)).stdout
    page_size = re.search(r'Page size:\s+([\d.]+) x ([\d.]+) pts', info)
    assert page_size, info
    if name != 'fitting-comparison':
        for actual, expected in zip(
                map(float, page_size.groups()), (fits[0].paper_width, fits[0].paper_height)):
            assert abs(actual - expected * TEX_PT_TO_BP) < PAGE_SIZE_TOLERANCE_BP, info
    text = run('pdftotext', str(pdf), '-').stdout
    if name == 'fitting-comparison':
        check_fitting_comparison(pdf, log, fits, pitches, text)
    elif name == 'fit':
        # Only the middle tree needs scaling, by less than 20%.
        assert fits[0].scale == fits[2].scale == 1 and .8 < fits[1].scale < 1
        pages = text.split('\f')
        assert 'stays on the first page' in pages[0]
        assert 'follows the tree on the next page' in pages[1]
    elif name == 'height':
        # This fixture needs a height reduction of less than 30%.
        assert .7 < fits[0].scale < 1
    elif name == 'labels':
        assert fits[0].smallest_font == 9 and fits[1].smallest_font == 10
    elif name == 'adaptive':
        assert [fit.minimum_font for fit in fits] == [10, 10, 9.5]
        assert fits[1].smallest_font > fits[0].smallest_font and pitches[1] > pitches[0]
        assert fits[2].smallest_font == fits[0].smallest_font and pitches[2] == pitches[0]
    elif name == 'override':
        assert 7 < fits[0].scale * fits[0].smallest_font < 8 and fits[0].minimum_font == 7
    elif name == 'curves':
        check_curves(pdf, log)
    elif name == 'roundness':
        check_roundness(pdf, log, fits)
    print(name, 'PASS', len(fits), 'trees')


def check_svg_sizing():
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


def check_fitting_overview(build_dir):
    # The overview must preserve the relative sizes of the two verified pages.
    overview = ROOT / 'examples/fitting-overview.tex'
    compile_document(build_dir, 'fitting-overview',
                     r'\AtBeginDocument{\graphicspath{{' + str(build_dir) +
                     r'/}}}\input{' + str(overview) + '}')
    info = run('pdfinfo', str(build_dir / 'fitting-overview.pdf')).stdout
    assert re.search(r'Pages:\s+1\b', info), info
    label_widths = []
    for pdf in ('fitting-comparison', 'fitting-overview'):
        result = run('pdftotext', '-bbox', str(build_dir / f'{pdf}.pdf'), '-')
        assert result.returncode == 0, result.stdout
        words = ET.fromstring(result.stdout).iter('{http://www.w3.org/1999/xhtml}word')
        label_widths.append([float(word.get('xMax')) - float(word.get('xMin'))
                             for word in words if word.text == 'alpha'])
    assert list(map(len, label_widths)) == [3, 2], 'Missing comparison labels'
    display_scales = [displayed / original for original, displayed in zip(*label_widths)]
    assert abs(display_scales[0] - display_scales[1]) < DISPLAY_SCALE_TOLERANCE, (
        'Unequal overview display scales')
    print('fitting-overview PASS (verified pages, one shared display scale)')


def check_rejections(build_dir):
    for name, error in (
        ('reject-small', 'the 8.0pt minimum'),
        ('reject-inner', 'requires normal'),
        ('reject-option', 'must be positive'),
        ('reject-font', 'Fitting requires 5pt'),
        ('reject-roundness', 'roundness must be a unitless number'),
    ):
        check_case(build_dir, name, error)

    for suffix, value, error in (
        ('above-max', '1.0001', 'roundness must be a unitless number'),
        ('unit', '1pt', 'roundness must be a unitless number'),
        ('text', 'banana', 'Package PGF Math Error'),
        ('nan', 'nan', 'roundness must be a unitless number'),
        ('infinity', 'inf', 'roundness must be a unitless number'),
    ):
        name = f'reject-roundness-{suffix}'
        compile_document(build_dir, name,
                         r'\def\BadRoundness{' + value + r'}\input{terminaltrees-tests/reject-roundness.tex}',
                         expected_error=error)
        print(name, 'PASS (expected rejection)')


def check_precision(build_dir):
    # Check the font floor against a 1000pt node at natural and reduced sizes.
    # Accept equality and reject a minimum one scaled point above the fitted font size.
    for width, minimum, offsets in (
        ('1100pt', '10pt', (-1, 0, 1)),
        ('500pt', '5pt', (-1, 0, 1)),
        # Without scale flooring, TeX rounds this width ratio up and the box overflows.
        ('800.012pt', '1pt', (0,)),
    ):
        for offset_sp in offsets:
            name = f'precision-{width}-{offset_sp}'
            log = compile_document(
                build_dir, name,
                r'\def\FitWidth{' + width + r'}\def\MinimumSize{\dimexpr ' +
                minimum + f'{offset_sp:+d}' + r'sp\relax}\input{terminaltrees-tests/precision.tex}',
                expected_error='Fitting requires' if offset_sp > 0 else None)
            if offset_sp > 0:
                print(name, 'PASS (expected rejection)')
            else:
                assert 'PRECISION PASS' in log, (name, log[-LOG_TAIL_LENGTH:])
                print(name, 'PASS')


def check_readme_examples(build_dir):
    examples = re.findall(r'```latex\n(.*?)```', (ROOT / 'README.md').read_text(), re.S)
    for example_index, example in enumerate(examples):
        if r'\documentclass' not in example:
            example = (r'\documentclass{article}\usepackage{terminaltrees}'
                       r'\begin{document}' + example + r'\end{document}')
        example = example.replace(r'\begin{document}',
                                  r'\input{terminaltrees-tests/trace.tex}\begin{document}')
        source = build_dir / f'guide-{example_index}.tex'
        source.write_text(example)
        log = compile_document(build_dir, source.stem, source)
        check_layout(log)
        print(f'guide-{example_index} PASS')


def check_readme_image(build_dir, options):
    # Validate the shared comparison before checking or updating its README image.
    example = (ROOT / 'examples/comparison.tex').read_text().replace(
        r'\begin{document}', r'\input{terminaltrees-tests/trace.tex}\begin{document}')
    source = build_dir / 'comparison.tex'
    source.write_text(example)
    log = compile_document(build_dir, source.stem, source)
    check_layout(log)
    result = run('pdftocairo', '-svg',
                 str(source.with_suffix('.pdf')), str(source.with_suffix('.svg')))
    assert result.returncode == 0, result.stdout
    svg = ET.parse(source.with_suffix('.svg')).getroot()
    assert list(svg.iter('{http://www.w3.org/2000/svg}path')), 'Missing vector paths'
    assert not list(svg.iter('{http://www.w3.org/2000/svg}image')), 'README image must remain vector'
    image = normalize_svg_size(source.with_suffix('.svg').read_bytes())
    source.with_suffix('.svg').write_bytes(image)
    if options.update_readme_image:
        (ROOT / 'examples/comparison.svg').write_bytes(image)
        print('comparison PASS (geometry checked, README image updated)')
    elif options.preview:
        print('comparison PASS (geometry checked, preview only)')
    else:
        assert image == (ROOT / 'examples/comparison.svg').read_bytes(), (
            'README comparison image changed. Run python3 terminaltrees-tests/check.py --update-readme-image')
        print('comparison PASS (geometry and exact rendered image)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    image_mode = parser.add_mutually_exclusive_group()
    image_mode.add_argument('--update-readme-image', action='store_true',
                           help='replace the README image after all rendering checks pass')
    image_mode.add_argument('--preview', action='store_true',
                           help='validate generated previews without comparing or changing the committed SVG')
    options = parser.parse_args()
    build_dir = Path(tempfile.mkdtemp(prefix='terminaltrees-check-'))
    print('Output directory:', build_dir, flush=True)

    check_svg_sizing()

    for name in ('fit', 'height', 'labels', 'adaptive', 'override',
                 'branches', 'centering', 'curves', 'roundness'):
        check_case(build_dir, name)
    check_case(build_dir, 'fitting-comparison', directory='examples')

    check_fitting_overview(build_dir)
    check_rejections(build_dir)
    check_precision(build_dir)
    check_readme_examples(build_dir)
    check_readme_image(build_dir, options)

    for source in (ROOT / 'terminaltrees.sty', ROOT / 'README.md'):
        print(hashlib.sha256(source.read_bytes()).hexdigest(), source.name)


if __name__ == '__main__':
    main()
