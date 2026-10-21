import { parse as parseYaml, stringify as stringifyYaml } from "yaml";

const MAX_CONVERSION_BYTES = 1_000_000;

function enforceInputLimit(input: string): void {
  if (new TextEncoder().encode(input).byteLength > MAX_CONVERSION_BYTES) {
    throw new Error("Limit input to one megabyte.");
  }
}

export function jsonToYaml(input: string): string {
  enforceInputLimit(input);
  return stringifyYaml(JSON.parse(input), { lineWidth: 0 });
}

export function yamlToJson(input: string): string {
  enforceInputLimit(input);
  const value = parseYaml(input, { maxAliasCount: 20 });
  return JSON.stringify(value === undefined ? null : value, null, 2);
}

export function convertCurrency(
  amount: number,
  source: string,
  target: string,
  rates: Record<string, number>,
): number {
  if (!Number.isFinite(amount) || amount < 0) throw new Error("Enter a non-negative amount.");
  const sourceRate = rates[source];
  const targetRate = rates[target];
  if (!sourceRate || !targetRate || !Number.isFinite(sourceRate) || !Number.isFinite(targetRate)) {
    throw new Error("Choose currencies with available reference rates.");
  }
  return (amount / sourceRate) * targetRate;
}

const MD5_SHIFTS = [
  7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
  5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
  4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
  6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];
const MD5_CONSTANTS = Array.from({ length: 64 }, (_, index) =>
  Math.floor(Math.abs(Math.sin(index + 1)) * 0x1_0000_0000),
);

/** MD5 for legacy checksums only; this digest is not suitable for security. */
export function md5Hex(input: string): string {
  const bytes = new TextEncoder().encode(input);
  if (bytes.byteLength > MAX_CONVERSION_BYTES) {
    throw new Error("Limit input to one megabyte.");
  }

  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const bitLength = bytes.length * 8;
  for (let byte = 0; byte < 8; byte += 1) {
    padded[paddedLength - 8 + byte] = Math.floor(bitLength / 2 ** (8 * byte)) & 0xff;
  }

  let a0 = 0x67452301;
  let b0 = 0xefcdab89 | 0;
  let c0 = 0x98badcfe | 0;
  let d0 = 0x10325476;

  for (let offset = 0; offset < padded.length; offset += 64) {
    const words = new Int32Array(16);
    for (let word = 0; word < 16; word += 1) {
      const index = offset + word * 4;
      words[word] =
        padded[index] |
        (padded[index + 1] << 8) |
        (padded[index + 2] << 16) |
        (padded[index + 3] << 24);
    }

    let a = a0;
    let b = b0;
    let c = c0;
    let d = d0;
    for (let index = 0; index < 64; index += 1) {
      let nonlinear: number;
      let wordIndex: number;
      if (index < 16) {
        nonlinear = (b & c) | (~b & d);
        wordIndex = index;
      } else if (index < 32) {
        nonlinear = (d & b) | (~d & c);
        wordIndex = (5 * index + 1) % 16;
      } else if (index < 48) {
        nonlinear = b ^ c ^ d;
        wordIndex = (3 * index + 5) % 16;
      } else {
        nonlinear = c ^ (b | ~d);
        wordIndex = (7 * index) % 16;
      }

      const sum = (a + nonlinear + MD5_CONSTANTS[index] + words[wordIndex]) | 0;
      const shift = MD5_SHIFTS[index];
      const rotated = (sum << shift) | (sum >>> (32 - shift));
      [a, d, c, b] = [d, c, b, (b + rotated) | 0];
    }

    a0 = (a0 + a) | 0;
    b0 = (b0 + b) | 0;
    c0 = (c0 + c) | 0;
    d0 = (d0 + d) | 0;
  }

  return [a0, b0, c0, d0]
    .flatMap((word) => [0, 8, 16, 24].map((shift) => (word >>> shift) & 0xff))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
