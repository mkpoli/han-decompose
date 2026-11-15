# Forms of han-compose

`custom-forms.tsv.gz`: what ids-input's `scripts/build_custom_cuts.py` wrote into han-compose as
`data/custom-forms.json.gz` (format 2, han-compose `main` on 2026-11-15), without its outlines:
per chain and component the host its form was cut from, the recipe (operator and parts lifted),
the scores that kept it, and how many host cuts its library holds in each place.

Sans: 446 CHISE entities and 7 zi.tools chains, 353 library cuts. Serif: 296 and 1, 189.

`expected.json` lists, per chain, the components where this project differs from that file;
`docs/reproduction.md` gives the account.

Fonts: Noto Sans CJK JP 2.004, Plangothic P1 and P2 2.9.5795, Noto Serif CJK JP 2.003 (SIL OFL
1.1); Jigmo, Jigmo2, Jigmo3 2025-09-12 (CC0 1.0). Descriptions: CHISE IDS (GPL-2.0-or-later),
Yi Bai's IDS data (MIT). Reference glyphs: GlyphWiki.
