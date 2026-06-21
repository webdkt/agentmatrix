"""List detection. 对应 render/list.ts。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..parse.color import parse_color
from ..parse.css import normalize_text
from ..types import SlideNode
from .media_cache import image_key


@dataclass
class ListStyleConfig:
    isNum: bool = False
    numberType: Optional[str] = None
    characterCode: Optional[str] = None


def list_style_config(value: str) -> ListStyleConfig:
    """list-style-type → PptxGenJS bullet config."""
    if value in ('decimal', 'decimal-leading-zero'):
        return ListStyleConfig(isNum=True)
    if value in ('lower-alpha', 'lower-latin'):
        return ListStyleConfig(isNum=True, numberType='alphaLcPeriod')
    if value in ('upper-alpha', 'upper-latin'):
        return ListStyleConfig(isNum=True, numberType='alphaUcPeriod')
    if value == 'lower-roman':
        return ListStyleConfig(isNum=True, numberType='romanLcPeriod')
    if value == 'upper-roman':
        return ListStyleConfig(isNum=True, numberType='romanUcPeriod')
    if value == 'circle':
        return ListStyleConfig(isNum=False, characterCode='25CB')
    if value == 'square':
        return ListStyleConfig(isNum=False, characterCode='25A0')
    return ListStyleConfig(isNum=False)


LIST_UNIFORM_KEYS = (
    'color',
    'fontWeight',
    'fontStyle',
    'fontFamily',
    'fontSize',
    'textDecorationLine',
    'textDecoration',
    'textDecorationStyle',
    'textDecorationColor',
    'textTransform',
    'letterSpacing',
    'textShadow',
)


def detect_list(node: SlideNode) -> Optional[List[str]]:
    """A <ul>/<ol> of uniformly-styled plain-text <li> → list of item strings, else None."""
    if node.tag not in ('ul', 'ol'):
        return None
    items: List[str] = []
    if not node.children:
        return None
    first = node.children[0]
    for li in node.children:
        if (
            li.tag != 'li'
            or li.style.get('visibility') == 'hidden'
            or li.style.get('opacity') == '0'
            or len(li.children) > 0
            or image_key(li)
            or parse_color(li.style.get('backgroundColor'))
        ):
            return None
        for k in LIST_UNIFORM_KEYS:
            if (li.style.get(k) or '') != (first.style.get(k) or ''):
                return None
        text = normalize_text(li.text, li.style.get('whiteSpace')) if li.text else ''
        if not text:
            return None
        items.append(text)
    return items if items else None
