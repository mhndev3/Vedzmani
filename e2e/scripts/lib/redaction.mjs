// Shared redaction rules for scripts/sanitize-results.mjs (Playwright JSON report) and
// scripts/redact-backend-log.mjs (backend log). Pure functions, no I/O, no output of any value.
//
// Design rules:
//  * Redaction and the post-check are separate functions. The post-check runs on the PARSED output (what a
//    reader of the artifact would see), never on JSON-escaped text, so `\"` / `\n` escaping cannot cause a
//    false positive or hide a leak.
//  * A sensitive KEY wins over the value: `{"otp": "..."}` is redacted because of the property name, not
//    because of what the value looks like.
//  * Playwright `Expected` / `Received` blocks are withheld including their continuation lines, because an
//    echoed value can span several lines (objects, arrays, diffs) and free text cannot be pattern-matched.

export const REDACTED = "[redacted]";
export const WITHHELD = "[value withheld]";
export const DIFF_WITHHELD = "[diff withheld]";
export const ELEMENT_WITHHELD = "[element withheld]";

// ---------- text normalisation ----------
const ANSI = /\u001b\[[0-9;]*[A-Za-z]/g;
export const normalizeText = (s) => s.replace(ANSI, "").replace(/\r\n?/g, "\n");

// ---------- sensitive keys ----------
const SENSITIVE_WORDS = new Set([
  "sessionid", "csrftoken", "cookie", "cookies", "authorization", "bearer", "token", "tokens", "otp", "otps",
  "code", "codes", "phone", "phones", "password", "passwords", "passwd", "secret", "secrets", "credential",
  "credentials",
]);

// Property-name check for parsed JSON: splits camelCase / snake_case / kebab-case into words.
export function isSensitiveKey(key) {
  const words = String(key)
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
  if (words.some((w) => SENSITIVE_WORDS.has(w))) return true;
  return /sessionid|csrftoken|setcookie|apikey/.test(words.join(""));
}

// Key names in free text (key=value, key: value, "key":"value", \"key\":\"value\").
const KEYWORDS =
  "sessionid|csrf[-_]?token|set-cookie|cookies?|authorization|bearer|tokens?|otp|codes?|phones?|passwords?|passwd|secrets?|credentials?|api[-_]?key";
const KEY_PLAIN = `(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[-_])*(?:${KEYWORDS})(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9])`;
// camelCase compounds (accessToken, otpCode, phoneNumber); case-sensitive on purpose.
const KEY_CAMEL =
  "(?<![A-Za-z0-9])(?:[a-z]+(?:Token|Code|Phone|Otp|OTP|Password|Secret|Cookie|Credential|ApiKey)|(?:token|code|phone|otp|password|secret|cookie|credential)[A-Z])[A-Za-z0-9]*(?![A-Za-z0-9])";
// Key, optional closing quote of the key (possibly backslash-escaped), separator. Separator whitespace never
// crosses a newline, so `code:\n next line` does not swallow the next line.
const keyRe = (src, flags) => new RegExp(`(${src})(\\\\*["']?)([ \\t]*[=:][ \\t]*)`, flags);
const KEY_REGEXES = () => [keyRe(KEY_PLAIN, "gi"), keyRe(KEY_CAMEL, "g")];

// Parses the value that starts at str[i]: escaped-quoted (\"x\"), quoted ("x" / 'x'), or bare.
function parseValue(str, i) {
  const rest = str.slice(i);
  if (rest.startsWith(REDACTED)) return { open: "", close: "", content: REDACTED, end: i + REDACTED.length };
  let m = /^(\\+)(["'])/.exec(rest);
  if (m) {
    const closer = m[1] + m[2];
    const from = i + closer.length;
    const nl = str.indexOf("\n", from);
    const limit = nl === -1 ? str.length : nl;
    const idx = str.indexOf(closer, from);
    if (idx !== -1 && idx <= limit) return { open: closer, close: closer, content: str.slice(from, idx), end: idx + closer.length };
    return { open: closer, close: "", content: str.slice(from, limit), end: limit };
  }
  m = /^(["'])/.exec(rest);
  if (m) {
    const q = m[1];
    let j = i + 1;
    while (j < str.length && str[j] !== "\n") {
      if (str[j] === "\\") {
        j += 2;
        continue;
      }
      if (str[j] === q) break;
      j++;
    }
    const end = Math.min(j, str.length);
    const closed = str[end] === q;
    return { open: q, close: closed ? q : "", content: str.slice(i + 1, end), end: closed ? end + 1 : end };
  }
  m = /^(?:(?:Bearer|Basic|Token)[ \t]+)?([^\s"'\\;,&}\])]+)/i.exec(rest);
  if (m) return { open: "", close: "", content: m[1], end: i + m[0].length };
  return null; // key with no value (e.g. `code:` at end of line)
}

function scanKeyValues(str, re, visit) {
  re.lastIndex = 0;
  let m;
  while ((m = re.exec(str))) {
    const start = m.index + m[0].length;
    const v = parseValue(str, start);
    if (!v) continue;
    visit(m, start, v);
    re.lastIndex = Math.max(v.end, re.lastIndex);
  }
}

export function redactKeyValues(str) {
  let out = str;
  for (const re of KEY_REGEXES()) {
    let result = "";
    let last = 0;
    scanKeyValues(out, re, (m, start, v) => {
      result += out.slice(last, start) + v.open + REDACTED + v.close;
      last = v.end;
    });
    out = result + out.slice(last);
  }
  return out;
}

export function keyValueProblems(str) {
  const problems = [];
  for (const re of KEY_REGEXES()) {
    scanKeyValues(str, re, (m, _start, v) => {
      if (v.content !== REDACTED) problems.push(`unredacted ${m[1].toLowerCase()} value`);
    });
  }
  return problems;
}

// ---------- phones, opaque tokens, header lines, html value attributes ----------
const PHONE_INTL = /(?:\+|00)?98[\s-]?9\d{2}[\s-]?\d{3}[\s-]?\d{4}/g;
const PHONE_LOCAL = /(?<!\d)09\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)/g;
const LONG_TOKEN = /\b[A-Za-z0-9_-]{32,}\b/g;
const HEADER_LINE = /\b(cookie|set-cookie|authorization)([ \t]*[=:][ \t]*)[^\n]*/gi;
const HTML_VALUE = /\bvalue=(["'])[^"'\n]*\1/gi;
const fresh = (re) => new RegExp(re.source, re.flags.replace("g", ""));

export const redactPhones = (s) => s.replace(PHONE_INTL, "[phone]").replace(PHONE_LOCAL, "[phone]");
export const phoneProblems = (s) => [
  ...(fresh(PHONE_INTL).test(s) ? ["international phone number"] : []),
  ...(fresh(PHONE_LOCAL).test(s) ? ["local phone number"] : []),
];
export const longTokenProblems = (s) => (fresh(LONG_TOKEN).test(s) ? ["long opaque token"] : []);

// Line-level redaction shared with the backend log (no Playwright-specific rules, no long-token rule).
export function redactSensitiveValues(s) {
  return redactPhones(redactKeyValues(s.replace(HEADER_LINE, "$1$2" + REDACTED)));
}
export function sensitiveValueProblems(s) {
  return [...new Set([...phoneProblems(s), ...keyValueProblems(s)])];
}

// ---------- Playwright Expected / Received / diff / call-log echoes ----------
const LABEL = /^([ \t>|-]*(?:Expected|Received)(?:[ \t]+[A-Za-z]+){0,3})[ \t]*:(.*)$/;
const DIFF_HEADER = /^[ \t]*[-+][ \t]+(?:Expected|Received)\b/;
const STOP =
  /^[ \t]*(?:Call log:|Locator:|Timeout:|Error:|Matcher error:|Expect "|Expecting\b|waiting for\b|\d+[ \t]*[×x][ \t]|[-•][ \t]+(?:Expect|expect|waiting|waited|locator|retry|attempt)\b)|^[ \t]+at[ \t].*:\d+(?::\d+)?\)?[ \t]*$/;
// Values that are state words / small counts, not echoed data. Kept for diagnostics.
const SAFE_STATE = /^(?:visible|hidden|attached|detached|enabled|disabled|checked|unchecked|editable|focused|empty|<element\(s\) not found>)$/i;
function isSafeEcho(labelText, value) {
  const v = value.trim();
  if (SAFE_STATE.test(v)) return true;
  return /\b(?:length|count)$/i.test(labelText.trim()) && /^\d{1,4}$/.test(v);
}

// Replaces echoed values with markers. Continuation lines of a withheld block are dropped (they can carry the
// rest of a multi-line object/array/string), up to the next structural Playwright line.
export function withholdEchoes(text) {
  const out = [];
  let mode = null; // "echo" | "diff" while skipping continuation lines
  for (const line of text.split("\n")) {
    if (STOP.test(line)) mode = null;
    if (DIFF_HEADER.test(line)) {
      if (mode !== "diff") out.push(DIFF_WITHHELD);
      mode = "diff";
      continue;
    }
    const label = LABEL.exec(line);
    if (label && mode !== "diff") {
      if (isSafeEcho(label[1], label[2])) {
        out.push(line);
        mode = null;
      } else {
        out.push(`${label[1]}: ${WITHHELD}`);
        mode = "echo";
      }
      continue;
    }
    if (mode) continue;
    out.push(
      line
        .replace(/(unexpected value)[ \t].*$/i, `$1 ${WITHHELD}`)
        .replace(/(locator resolved to)[ \t]+<.*$/i, `$1 ${ELEMENT_WITHHELD}`)
        .replace(/^([ \t]*\d+\)[ \t]*)<.*$/, `$1${ELEMENT_WITHHELD}`),
    );
  }
  return out.join("\n");
}

export function echoProblems(text) {
  const problems = [];
  let mode = null;
  for (const line of text.split("\n")) {
    if (STOP.test(line)) mode = null;
    if (DIFF_HEADER.test(line)) {
      problems.push("diff block not withheld");
      continue;
    }
    const label = LABEL.exec(line);
    if (label) {
      const word = /Expected/.test(label[1]) ? "Expected" : "Received";
      if (label[2].trim() !== WITHHELD && !isSafeEcho(label[1], label[2])) problems.push(`${word} value not withheld`);
      mode = label[2].trim() === WITHHELD ? "echo" : null;
      continue;
    }
    if (mode && line.trim() !== "" && line.trim() !== DIFF_WITHHELD) problems.push("Expected/Received continuation line not withheld");
    if (/unexpected value[ \t]+(?!\[value withheld\])\S/i.test(line)) problems.push("unexpected-value echo not withheld");
    if (/locator resolved to[ \t]+<|^[ \t]*\d+\)[ \t]*</.test(line)) problems.push("element dump not withheld");
  }
  return problems;
}

// ---------- full text rules for the Playwright report ----------
export function redactText(s) {
  let t = withholdEchoes(normalizeText(s));
  t = t.replace(HEADER_LINE, "$1$2" + REDACTED);
  t = redactKeyValues(t);
  t = t.replace(HTML_VALUE, `value=$1${REDACTED}$1`);
  return redactPhones(t).replace(LONG_TOKEN, "[token]");
}

export function textProblems(s) {
  const t = normalizeText(s);
  const problems = [...phoneProblems(t), ...longTokenProblems(t), ...keyValueProblems(t), ...echoProblems(t)];
  if (/\bvalue=(["'])(?!\[redacted\]\1)/i.test(t)) problems.push("html value attribute not redacted");
  return problems;
}

// ---------- JSON tree (properties, not just text) ----------
// A cookie/header-style pair {"name": "Cookie", "value": "..."} is sensitive through its NAME.
const pairIsSensitive = (obj) => ["name", "key"].some((k) => typeof obj[k] === "string" && isSensitiveKey(obj[k]));

export function redactTree(node, key = "", sensitive = false) {
  if (node === null || node === undefined) return node;
  if (typeof node === "object") {
    if (Array.isArray(node)) return node.map((n) => redactTree(n, key, sensitive));
    const pair = pairIsSensitive(node);
    return Object.fromEntries(
      Object.entries(node).map(([k, v]) => [k, redactTree(v, k, sensitive || isSensitiveKey(k) || (pair && k === "value"))]),
    );
  }
  if (sensitive) return REDACTED; // string, number or boolean under a sensitive key
  if (typeof node === "string") return key === "id" ? node : redactText(node); // "id" = Playwright test hash
  return node;
}

const keyLabel = (k) => (/^[A-Za-z][A-Za-z0-9_-]{0,30}$/.test(k) ? k.toLowerCase() : "(unusual key)");

// Independent check on the parsed output.
export function treeProblems(node, key = "", sensitive = false) {
  if (node === null || node === undefined) return [];
  if (typeof node === "object") {
    if (Array.isArray(node)) return node.flatMap((n) => treeProblems(n, key, sensitive));
    const pair = pairIsSensitive(node);
    return Object.entries(node).flatMap(([k, v]) =>
      treeProblems(v, k, sensitive || isSensitiveKey(k) || (pair && k === "value")),
    );
  }
  if (sensitive) return node === REDACTED ? [] : [`unredacted ${keyLabel(key)} property`];
  if (typeof node === "string") return key === "id" ? [] : textProblems(node);
  return [];
}

// Serialised-text safety net, independent of structure: catches sensitive shapes in places the tree walk does not
// rewrite (for example object KEY names). Digits and token characters are not affected by JSON escaping.
export function serializedProblems(text) {
  const withoutIds = text.replace(/"id":\s*"[^"]*"/g, '"id":""');
  return [...phoneProblems(withoutIds), ...longTokenProblems(withoutIds)];
}
