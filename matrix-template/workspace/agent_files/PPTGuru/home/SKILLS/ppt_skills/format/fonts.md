# Font System

## Selection Principles

1. **Language matching**: When the user's query is in Chinese or requests a Chinese PPT, both Chinese and English fonts need to be specified; otherwise, only English fonts need to be set.
2. **Selection approach**: It is recommended to prioritize highly readable fonts for body text, and use stylized fonts + special design treatments (all caps, expanded letter spacing, bold, italic, etc.) for titles or special pages to enhance the style.
3. The font combination should support the overall visual style positioning.
4. **Name consistency**: **Make sure the font name is exactly consistent, including capitalization and spaces, to ensure the model can use it correctly.**

## Featured Fonts (Recommended)

These fonts offer distinctive styles and strong visual character. Prioritize these for creative and brand-forward presentations.

### English Fonts

| Font Name | Font Type | Style & Characteristics | Use Cases | Stylized Font |
|---|---|---|---|---|
| Liter | Sans-serif | Modern neo-grotesque style, low contrast, well-proportioned, optimized for screen display, clean and rational | Technology, product | No |
| HedvigLettersSans | Sans-serif | "Non-designer perspective" design, slightly irregular, distinctive personality, strong brand identity | Creative design, branding | No |
| Oranienbaum | Serif | Modern high-contrast serif, strong geometric feel, elegant lines, classical temperament | Culture, art, fashion | No |
| QuattrocentoSans | Sans-serif | Classic elegant sans-serif, gentle, highly readable, clear at small sizes | Academic, corporate, education | No |
| SortsMillGoudy | Serif | Revival of Goudy Old Style with classical print aesthetics, soft serifs, excellent readability | Literature, humanities | No |
| Unna | Serif | Neoclassical serif, pronounced vertical rhythm, elegance with strength | Literature, publishing, academic | Yes |
| Coda | Sans-serif | Rounded and friendly, soft curves, high openness | Business, friendly brand tone | Yes |
| Jersey15 | Sans-serif (sporty) | Sports jersey style, structured and square, pronounced grid feel (English + numbers only) | Sports, tech showcase pages | Yes |
| Jersey20Charted | Pixel font (gridded) | Sports number style with gridded texture overlay, enhanced athletic texture (English + numbers only) | Sports, mechanical, decorative showcase pages | Yes |

### Chinese Fonts

| Font Name | Font Type | Style & Characteristics | Use Cases | Usage Restrictions |
|---|---|---|---|---|
| MiSans | Sans-serif (Hei) | Xiaomi system font, clean and modern, variable weight, excellent screen rendering (multilingual support) | Technology, corporate, product | No |
| Noto Sans SC | Sans-serif (Hei) | Source Han Sans fork, well-structured, neutral style, extremely wide coverage. **Due to widespread use, please use sparingly** | Report-style | No |
| siyuanSongti | Serif (Song) | Source Han Serif, refined Song structure, contrasting strokes, elegant reading experience (multilingual support) | Literature, design, formal presentations | No |
| alimamadaoliti | Calligraphic (Lishu) | Alibaba Dao Li Ti, clerical script style, sharp brush strokes, combining strength with archaic charm | Chinese traditional style, culture, art exhibitions | No |
| alimamadongfangdakai | Calligraphic (Kai) | Alibaba Dongfang Da Kai, based on Yan-style calligraphy, full and rounded, bold and powerful | Culture, brand launches, Chinese traditional style | No |
| alimamashuheiti | Sans-serif (Hei) | Alibaba Shu Hei Ti, geometric sans-serif, uniform and structured, strong commercial feel | Business, technology, e-commerce | No |
| zhankuwenyiti | Handwritten | Zhanku Wenyi Ti, clean and fresh, slightly handwritten feel, strong artistic atmosphere | Light design, lifestyle | No |
| feibozhengdianti | Calligraphic (Brush) | Feibo Zhengdian Ti, brush writing style, heavy strokes, powerful | Film posters, e-commerce, brand showcase | No |
| deyihei | Sans-serif (Oblique Hei) | Deyi Hei, slender oblique sans-serif, combining humanist and geometric qualities, strong modern feel. **Does not support non-italic** | Creative technology, brand showcase | No |
| xiawuxinzhisong | Serif (Song) | LXGW Xin Zhi Song, based on IPAmj Mincho, bright, elegant, well-structured | Literature, classical style, print style | No |

### Mixed CJK-Latin Fonts

| Font Name | Font Type | Style & Characteristics | Use Cases | Usage Restrictions |
|---|---|---|---|---|
| jingpindianzhenTi | Pixel font | Jingpin Pixel Font, 9x9 dot matrix pixel style, strong retro electronic feel | Games, technology, pixel art | Yes |
| LXGW Bright | Serif (Fangsong/Kai) | LXGW Bright, combining Fangsong and Kai characteristics, gentle and clear letterforms | Literature, education, humanities | No |
| ZCOOL KuaiLe | Handwritten (Rounded) | Zhanku KuaiLe, lively and cute, playful and cartoon-like, youthful and energetic | Animation, children's, entertainment | No |

## System Fonts Fallback

When featured fonts are unavailable or maximum compatibility is required, use these widely-installed system fonts.

### Sans-Serif (Body Text, Modern Titles)

| Font Name | Latin/CJK | Character Sets | Recommended Use |
|-----------|-----------|----------------|-----------------|
| Arial | Latin | Latin | English body text, data, labels |
| Helvetica | Latin | Latin | Professional body text, Swiss style |
| Calibri | Latin | Latin | Microsoft ecosystem, clean body |
| Segoe UI | Latin | Latin | Modern UI style, Windows ecosystem |
| Roboto | Latin | Latin | Material design, Android style |
| Open Sans | Latin | Latin | Neutral, highly readable |
| PingFang SC | CJK + Latin | Simplified Chinese, Latin | Apple ecosystem, modern |
| Microsoft YaHei | CJK + Latin | Simplified Chinese, Latin | Windows default CJK, safe choice |
| Source Han Sans / Source Han Sans SC | CJK + Latin | Simplified Chinese, Latin | Adobe's CJK font, professional |
| WenQuanYi Micro Hei | CJK + Latin | Simplified Chinese, Latin | Open source, Linux compatible |

### Serif (Authoritative Titles, Formal Documents)

| Font Name | Latin/CJK | Character Sets | Recommended Use |
|-----------|-----------|----------------|-----------------|
| Times New Roman | Latin | Latin | Classic, formal, academic |
| Georgia | Latin | Latin | Web-friendly serif, readable |
| Noto Serif SC | CJK + Latin | Simplified Chinese, Latin | Formal CJK documents |
| Source Han Serif / Source Han Serif SC | CJK + Latin | Simplified Chinese, Latin | Adobe's CJK serif, elegant |
| Songti SC | CJK + Latin | Simplified Chinese, Latin | Traditional Chinese document style |
| SimSun | CJK + Latin | Simplified Chinese, Latin | Windows default serif |
| Libre Baskerville | Latin | Latin | Elegant, literary |
| Merriweather | Latin | Latin | High x-height, screen readable |
| Playfair Display | Latin | Latin | High contrast, fashion/luxury |
| Lora | Latin | Latin | Modern serif with calligraphic roots |

### Display / Decorative (Use Sparingly)

| Font Name | Latin/CJK | Character Sets | Recommended Use |
|-----------|-----------|----------------|-----------------|
| Impact | Latin | Latin | Bold headlines, posters |
| Bebas Neue | Latin | Latin | All-caps titles, modern |
| Montserrat | Latin | Latin | Geometric, tech, modern |
| Oswald | Latin | Latin | Condensed, headlines |
| Raleway | Latin | Latin | Elegant, thin weight titles |
| Poppins | Latin | Latin | Geometric, friendly, modern |
| Lato | Latin | Latin | Humanist sans, warm |

### Monospace (Code, Data Tables, Technical Content)

| Font Name | Latin/CJK | Character Sets | Recommended Use |
|-----------|-----------|----------------|-----------------|
| Courier New | Latin | Latin | Classic monospace, code |
| Consolas | Latin | Latin | Modern monospace, Windows |
| Monaco | Latin | Latin | macOS default monospace |
| JetBrains Mono | Latin | Latin | Developer-focused, ligatures |
| Fira Code | Latin | Latin | Coding font with ligatures |
| Source Code Pro | Latin | Latin | Adobe's open source monospace |
| Noto Sans Mono SC | CJK + Latin | Simplified Chinese, Latin | CJK monospace |

## Font Pairing Recommendations

### Business / Consulting (business_insight profile)
- **Titles**: Serif Bold (e.g., "Times New Roman" or "Noto Serif SC")
- **Body**: Sans-serif (e.g., "Arial" or "MiSans")
- **Chinese pairing**: "Arial, Microsoft YaHei"

### Academic (academic profile)
- **Titles**: Serif (e.g., "Times New Roman" or "Noto Serif SC")
- **Body**: Serif or Sans-serif (e.g., "Times New Roman" or "Arial")
- **Chinese pairing**: "Times New Roman, SimSun" or "Arial, Microsoft YaHei"

### Technology / Modern (general profile)
- **Titles**: Geometric Sans-serif (e.g., "Montserrat" or "Poppins")
- **Body**: Clean Sans-serif (e.g., "Open Sans" or "MiSans")
- **Chinese pairing**: "Montserrat, MiSans" or "Poppins, PingFang SC"

### Education (education profile)
- **Titles**: Friendly Sans-serif (e.g., "Poppins" or "Lato")
- **Body**: Highly readable Sans-serif (e.g., "Open Sans" or "MiSans")
- **Chinese pairing**: "Poppins, MiSans" or "Lato, Microsoft YaHei"

## Font Specification Format

In PPTD, specify dual fonts for CJK and Latin:

```yaml
fontFamily: "Arial, Microsoft YaHei"
```

Format: `"LatinFont, CJKFont"`

- The first font is used for Latin characters
- The second font is used for CJK characters
- If only one font is specified, it is used for all characters

## Notes

1. **Font availability**: Not all fonts may be available in all environments. Prefer widely available fonts (Arial, Times New Roman, Microsoft YaHei, MiSans) for maximum compatibility.
2. **Font embedding**: When using custom fonts, ensure they are embedded or available in the target environment.
3. **Fallback**: The PPTD renderer will use system fallback fonts if a specified font is not available.
4. **CJK considerations**: CJK fonts are significantly larger than Latin fonts. Consider font subsetting or using web fonts when file size is a concern.
