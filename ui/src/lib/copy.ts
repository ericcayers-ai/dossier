/** Small words, correctly, everywhere.
 *
 *  The UI used to say `3 file(s)`, `1 posting(s) archived`, `2 day(s)` — the
 *  placeholder style of a log line, printed at the size of a sentence. A reader
 *  notices `(s)` immediately and it is one of the cheapest tells that a screen
 *  was assembled rather than written.
 */
export function count(n: number, one: string, many?: string): string {
  return `${n} ${n === 1 ? one : many ?? `${one}s`}`;
}

/** For the verb after a count: `count(1,'row') + (isOne(1) ? ' needs' : ' need')`. */
export function isOne(n: number): boolean {
  return n === 1;
}

/** `applied_roles` -> `Applied roles`: a field name shown to a person, not to a log. */
export function humanise(key: string): string {
  const words = key.replace(/[_-]+/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
