import { expect, test } from "bun:test";
import { OPERATOR_LINES } from "../src/lib/operators.ts";

const ALL = [..."⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿼⿽⿾⿿㇯〾"];

test("every operator has a drawing", () => {
  expect(Object.keys(OPERATOR_LINES).sort()).toEqual([...ALL].sort());
  expect(ALL.slice(0, 16).map((c) => c.codePointAt(0))).toEqual(Array.from({ length: 16 }, (_, i) => 0x2ff0 + i));
});

test("no two operators share a drawing", () => {
  const paths = Object.values(OPERATOR_LINES);
  expect(new Set(paths).size).toBe(paths.length);
});
