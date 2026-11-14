# han-decompose

han-decompose records, for each Han character a font draws, which of the glyph's contours belong
to which component of its ideographic description sequence (IDS). Every part is a set of contours
the font already draws.

Its sibling [han-compose](https://github.com/mkpoli/han-compose) draws a character from its
description.

## Licences

Code is under the MIT licence (`LICENSE`).

Data files are outside it. Each data file keeps the licence of the font its outlines come from and
lists the terms of the description sources its labels were read from.
