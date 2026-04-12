export interface InjectionResult {
  detected: boolean;
  reasons: string[];
}

const INJECTION_PATTERNS = [
  { pattern: /ignore\s+(all\s+)?previous\s+instructions/i, label: 'injection pattern: "ignore previous instructions"' },
  { pattern: /ignore\s+(all\s+)?above\s+instructions/i, label: 'injection pattern: "ignore above instructions"' },
  { pattern: /disregard\s+(all\s+)?previous/i, label: 'injection pattern: "disregard previous"' },
  { pattern: /you\s+are\s+now\s+a/i, label: 'injection pattern: "you are now a"' },
  { pattern: /^system\s*:/im, label: 'injection pattern: "system:" prefix' },
  { pattern: /^(human|user|assistant)\s*:/im, label: 'injection pattern: role prefix' },
  { pattern: /output\s+(your|the)\s+system\s+prompt/i, label: 'injection pattern: prompt extraction' },
  { pattern: /reveal\s+(your|the)\s+(secret|hidden|system)/i, label: 'injection pattern: secret extraction' },
];

const HTML_PATTERN = /<\s*(script|iframe|object|embed|form|input|link|meta|style)\b/i;
const ZERO_WIDTH_PATTERN = /[\u200B\u200C\u200D\u2060\uFEFF]/;
const RTL_OVERRIDE_PATTERN = /[\u202A-\u202E\u2066-\u2069]/;
const BASE64_PATTERN = /[A-Za-z0-9+/]{20,}={0,2}/;
const MAX_FIELD_LENGTH = 5000;

export function detectInjection(text: string): InjectionResult {
  const reasons: string[] = [];

  for (const { pattern, label } of INJECTION_PATTERNS) {
    if (pattern.test(text)) {
      reasons.push(label);
    }
  }

  if (HTML_PATTERN.test(text)) {
    reasons.push('HTML/script tag detected');
  }

  if (ZERO_WIDTH_PATTERN.test(text)) {
    reasons.push('suspicious unicode: zero-width characters');
  }

  if (RTL_OVERRIDE_PATTERN.test(text)) {
    reasons.push('suspicious unicode: RTL override characters');
  }

  if (text.length > MAX_FIELD_LENGTH) {
    reasons.push(`anomalous length: ${text.length} chars (max ${MAX_FIELD_LENGTH})`);
  }

  if (BASE64_PATTERN.test(text)) {
    reasons.push('possible base64 encoded payload');
  }

  return { detected: reasons.length > 0, reasons };
}

export function scanEntry(entry: Record<string, unknown>): InjectionResult {
  const textFields = ['title', 'summary', 'blockquote', 'blockquote_source'] as const;
  const allReasons: string[] = [];

  for (const field of textFields) {
    const value = entry[field];
    if (typeof value === 'string') {
      const result = detectInjection(value);
      if (result.detected) {
        allReasons.push(...result.reasons.map((r) => `[${field}] ${r}`));
      }
    }
  }

  return { detected: allReasons.length > 0, reasons: allReasons };
}
