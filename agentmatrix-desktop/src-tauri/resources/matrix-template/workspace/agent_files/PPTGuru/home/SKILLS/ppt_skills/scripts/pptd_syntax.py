#!/usr/bin/env python3
"""
PPTD Syntax — schema-driven structural validation for PPTD files.

Detects: unknown/misspelled fields, wrong types, cross-element-type violations,
and structural nesting errors (e.g. text at element level instead of inside content).
"""


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------

def levenshtein(s1, s2):
    """Edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (c1 != c2)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


def suggest_field(field, known_fields, max_distance=3):
    """Return closest known field name, or '' if none within max_distance."""
    best = ''
    best_dist = max_distance + 1
    for known in known_fields:
        d = levenshtein(field, known)
        if d < best_dist:
            best_dist = d
            best = known
    return best if best_dist <= max_distance else ''


# ---------------------------------------------------------------------------
# Type checking
# ---------------------------------------------------------------------------

def check_type(spec, value):
    """Validate value against a type spec string. Returns True if ok.

    Specs: 'str', 'int', 'float', 'bool', 'list', 'dict',
           'str_color', 'number_0_1', 'number_positive',
           'list_of_2_numbers', 'list_of_2_bools', 'list_of_4_numbers',
           'list_of_numbers',
           None = any type (always ok)
    """
    if spec is None:
        return True
    if value is None:
        return True  # null is valid for any spec (e.g. fill: null = no fill)
    if spec == 'str':
        return isinstance(value, str)
    if spec == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == 'float':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == 'bool':
        return isinstance(value, bool)
    if spec == 'list':
        return isinstance(value, list)
    if spec == 'dict':
        return isinstance(value, dict)
    if spec == 'str_color':
        return isinstance(value, str) and (value.startswith('#') or value.startswith('$'))
    if spec == 'number_0_1':
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    if spec == 'number_positive':
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    if spec == 'list_of_2_numbers':
        return (isinstance(value, list) and len(value) == 2 and
                all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in value))
    if spec == 'list_of_2_bools':
        return (isinstance(value, list) and len(value) == 2 and
                all(isinstance(b, bool) for b in value))
    if spec == 'list_of_4_numbers':
        return (isinstance(value, list) and len(value) == 4 and
                all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in value))
    if spec == 'list_of_numbers':
        return (isinstance(value, list) and
                all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in value))
    return True  # Unknown spec → accept


# ---------------------------------------------------------------------------
# Schema format: {'required': set, 'optional': {field: type_spec}}
# ---------------------------------------------------------------------------

ROOT_SCHEMA = {
    'required': {'theme', 'size', 'pages'},
    'optional': {
        'title': 'str',
        'slideWidth': 'float',
        'slideHeight': 'float',
        'sourceTemplate': 'str',
    },
}

PAGE_SCHEMA = {
    'required': {'pageType', 'elements'},
    'optional': {
        'layoutIndex': 'int',
        'layoutName': 'str',
        'background': 'dict',
        'notes': 'str',
    },
}

ELEMENT_BASE_SCHEMA = {
    'required': {'elementId', 'elementType', 'bounds'},
    'optional': {
        'opacity': 'number_0_1',
        'rotation': 'float',
        'flip': 'list_of_2_bools',
        'border': 'dict',
        'shadow': 'dict',
        'fill': 'dict',
        'placeholder': 'dict',
    },
}

# Fields allowed per elementType (beyond the base fields)
ELEMENT_TYPE_FIELDS = {
    'text': {'content', 'shapeName'},
    'shape': {'shapeName', 'adjustments', 'path', 'arrow'},
    'image': {'src', 'shapeName', 'adjustments', 'fit', 'crop'},
    'icon': {'iconName'},
    'table': {'columnWidths', 'rowHeights', 'rows', 'style', 'tableStyleId'},
    'chart': {
        'type', 'data', 'x', 'y', 'names', 'colors', 'options',
        'seriesStyle', 'xAxis', 'yAxis', 'title', 'legend',
        'dataLabels', 'size', 'secondaryAxis',
    },
}

TEXT_CONTENT_SCHEMA = {
    'required': {'text'},
    'optional': {
        'style': None,  # str (theme ref like "$title") or dict (inline style)
        'fontSize': 'float',
        'fontFamily': 'str',
        'color': 'str_color',
        'lineHeight': 'float',
        'lineHeightPx': 'float',
        'letterSpacing': 'float',
        'marginTop': 'float',
        'textDirection': 'str',
        'wrap': 'bool',
        'align': 'list',
        'gradient': 'dict',
        'shadow': 'dict',
    },
}

FILL_SOLID_SCHEMA = {
    'required': {'type'},
    'optional': {
        'color': 'str_color',
    },
}

FILL_GRADIENT_SCHEMA = {
    'required': {'type', 'gradientType', 'stops'},
    'optional': {
        'angle': 'float',
    },
}

FILL_IMAGE_SCHEMA = {
    'required': {'type', 'src'},
    'optional': {
        'fit': 'dict',
        'crop': 'dict',
        'mask': 'dict',
        'opacity': 'number_0_1',
    },
}

BORDER_SCHEMA = {
    'required': {'style'},
    'optional': {
        'color': 'str_color',
        'width': 'float',
    },
}

SHADOW_SCHEMA = {
    'required': {'blur', 'color'},
    'optional': {
        'offset': 'list_of_2_numbers',
    },
}

TABLE_CELL_SCHEMA = {
    'required': set(),
    'optional': {
        'content': 'dict',
        'fill': None,  # can be dict (Fill) or str (color ref)
        'border': None,  # can be dict or list
        'rowSpan': 'int',
        'colSpan': 'int',
    },
}

# Sub-schemas for nested structures
COLOR_STOP_SCHEMA = {
    'required': {'position', 'color'},
    'optional': {},
}

IMAGE_FIT_SCHEMA = {
    'required': {'mode'},
    'optional': {},
}

IMAGE_CROP_SCHEMA = {
    'required': set(),
    'optional': {
        'left': 'number_0_1',
        'top': 'number_0_1',
        'right': 'number_0_1',
        'bottom': 'number_0_1',
    },
}

MARKER_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'shape': 'str',
        'fill': 'dict',
        'border': 'dict',
        'size': 'number_positive',
    },
}

CHART_TITLE_CONFIG_SCHEMA = {
    'required': {'text'},
    'optional': {
        'color': 'str_color',
        'fontSize': 'float',
    },
}

AXIS_LABEL_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'color': 'str_color',
        'fontSize': 'float',
    },
}

AXIS_LINE_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'style': 'str',
        'color': 'str_color',
        'width': 'float',
        'arrow': 'bool',
    },
}

AXIS_TITLE_CONFIG_SCHEMA = {
    'required': {'text'},
    'optional': {
        'color': 'str_color',
        'fontSize': 'float',
    },
}

CHART_OPTIONS_SCHEMA = {
    'required': set(),
    'optional': {
        'direction': 'str',
        'barWidth': 'number_0_1',
        'innerRadius': 'number_0_1',
        'startAngle': 'float',
        'stacked': None,  # true or '100%'
        'nullHandling': 'str',
        'fontFamily': 'str',
    },
}

SERIES_STYLE_SCHEMA = {
    'required': set(),
    'optional': {
        'name': 'str',
        'fill': 'dict',
        'border': 'dict',
        'smooth': 'bool',
        'line': 'str',
        'width': 'number_positive',
        'marker': None,  # false or dict
        'type': 'str',
        'axis': 'str',
        'dataLabels': 'dict',
    },
}

AXIS_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'show': 'bool',
        'label': None,  # bool or dict
        'axisLine': None,  # bool or dict
        'gridLine': None,  # bool or dict
        'min': 'float',
        'max': 'float',
        'numberFormat': 'str',
        'title': None,  # str or dict
    },
}

LEGEND_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'show': 'bool',
        'position': 'str',
        'color': 'str_color',
        'fontSize': 'float',
    },
}

DATA_LABEL_CONFIG_SCHEMA = {
    'required': set(),
    'optional': {
        'show': 'bool',
        'content': 'str',
        'color': 'str_color',
        'numberFormat': 'str',
        'fontSize': 'float',
    },
}

THEME_TEXT_STYLE_SCHEMA = {
    'required': set(),
    'optional': {
        'color': 'str_color',
        'fontSize': 'float',
        'fontFamily': 'str',
        'fontStyle': 'str',
        'backgroundColor': 'str_color',
        'lineHeight': 'float',
        'lineHeightPx': 'float',
        'letterSpacing': 'float',
        'marginTop': 'float',
    },
}

THEME_TABLE_STYLE_SCHEMA = {
    'required': set(),
    'optional': {
        'fontSize': 'float',
        'fontFamily': 'str',
        'fill': 'dict',
        'headerFill': 'str_color',
        'headerColor': 'str_color',
        'headerBold': 'bool',
        'headerBorder': None,  # Border | [Border|null] | [Border|null]x4
        'bodyFill': 'list',
        'bodyColor': 'str_color',
        'bodyBorder': None,
        'lastRowBorder': None,
        'firstColumnFill': 'str_color',
        'firstColumnColor': 'str_color',
        'firstColumnBold': 'bool',
        'border': None,
    },
}


# ---------------------------------------------------------------------------
# Core validation functions
# ---------------------------------------------------------------------------

def validate_fields(data, schema, add_error_fn, prefix=''):
    """Check unknown fields (with Levenshtein suggestions) + type validation.

    Args:
        data: dict to validate
        schema: {'required': set, 'optional': {field: type_spec}}
        add_error_fn: callback(loc, msg) for reporting errors
        prefix: location prefix for error messages
    """
    if not isinstance(data, dict):
        return

    required = schema.get('required', set())
    optional = schema.get('optional', {})
    all_known = required | set(optional.keys())

    # Check required fields
    for field in required:
        if field not in data:
            add_error_fn(prefix, f'Missing required field: {field}')

    # Check unknown fields + type validation
    for field, value in data.items():
        if field in required or field in optional:
            # Type check
            spec = optional.get(field) if field in optional else None
            if field in required:
                # Required fields don't have type specs in the required set;
                # check optional dict for type if defined there
                spec = optional.get(field)
            if spec is not None and not check_type(spec, value):
                add_error_fn(prefix, f'Field "{field}" type error: expected {spec}')
        else:
            # Unknown field — suggest correction
            suggestion = suggest_field(field, all_known)
            if suggestion:
                add_error_fn(prefix, f'Unknown field: {field}. Did you mean: {suggestion}?')
            else:
                add_error_fn(prefix, f'Unknown field: {field}')


def check_element_type_fields(elem, add_error_fn, prefix=''):
    """Report fields not belonging to this elementType.

    Checks that element only contains base fields + its type-specific fields.
    """
    if not isinstance(elem, dict):
        return

    elem_type = elem.get('elementType')
    if not elem_type or elem_type not in ELEMENT_TYPE_FIELDS:
        return

    base_fields = ELEMENT_BASE_SCHEMA['required'] | set(ELEMENT_BASE_SCHEMA['optional'].keys())
    type_fields = ELEMENT_TYPE_FIELDS.get(elem_type, set())
    allowed = base_fields | type_fields

    for field in elem:
        if field not in allowed:
            add_error_fn(prefix, f"Field '{field}' is not valid for elementType='{elem_type}'")


def check_text_level(elem, add_error_fn, prefix=''):
    """Detect 'text' field at element level instead of inside content.

    Common AI error: placing text directly on the element dict rather than
    inside content.text.
    """
    if not isinstance(elem, dict):
        return
    if elem.get('elementType') != 'text':
        return
    if 'text' in elem and 'content' not in elem:
        add_error_fn(prefix, "Field 'text' must be inside 'content', not at element level")
    elif 'text' in elem and 'content' in elem:
        add_error_fn(prefix, "Field 'text' should not be at element level (use content.text)")
