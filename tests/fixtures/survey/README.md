# Surveys of ids-input

What ids-input's component survey wrote, to hold this project's survey against.

| File | From |
|---|---|
| `山.tsv.gz` | ids-input `data/mountain-instances.json.gz`, built 2026-11-03 on branch `feat/donor-parts`: 2,150 characters, 2,220 instances. |
| `口.tsv.gz` | ids-input `data/component-instances-口.json.gz`, built 2026-11-09 on the same branch: 4,731 characters, 5,033 instances. |

Columns: the character, the tree its reading was made on, how many components deep the tree was
spelled out, and its instances, each as `depth:fit:filled:skeleton` (the number of operands walked
down to it, its likeness to the component drawn alone, 1 − IoU, and the one-sided skeleton
distance), separated by spaces.

`expected.json` lists, per component, the characters where this project differs from that file
and why; `docs/reproduction.md` gives the account.

Fonts: Noto Sans CJK JP 2.004, Plangothic P1 and P2 2.9.5795 (SIL OFL 1.1). Descriptions:
BabelStone IDS, Andrew West, File Date 2025-06-27.
