/**
 * Quantized Token Frequency Elias Gamma & Delta Codec
 * Universal variable-length bitstream compression for positive integers,
 * ideal for power-law distributed token frequencies and inverted list deltas.
 */

class BitStreamWriter {
  constructor() {
    this.bits = [];
  }

  writeBit(b) {
    this.bits.push(b ? 1 : 0);
  }

  writeUnary(n) {
    for (let i = 0; i < n; i++) this.writeBit(0);
    this.writeBit(1);
  }

  writeBits(val, count) {
    for (let i = count - 1; i >= 0; i--) {
      this.writeBit((val >> i) & 1);
    }
  }

  getBitString() {
    return this.bits.join('');
  }
}

class BitStreamReader {
  constructor(bitString) {
    this.bits = bitString;
    this.pos = 0;
  }

  readBit() {
    if (this.pos >= this.bits.length) return null;
    return this.bits[this.pos++] === '1' ? 1 : 0;
  }

  readUnary() {
    let count = 0;
    while (true) {
      const bit = this.readBit();
      if (bit === null) return null;
      if (bit === 1) break;
      count++;
    }
    return count;
  }

  readBits(count) {
    let val = 0;
    for (let i = 0; i < count; i++) {
      const bit = this.readBit();
      if (bit === null) return null;
      val = (val << 1) | bit;
    }
    return val;
  }
}

class EliasCodec {
  // Elias Gamma Encode (positive integers >= 1)
  static encodeGamma(n) {
    if (n < 1) throw new Error('Elias Gamma only supports positive integers >= 1');
    const writer = new BitStreamWriter();
    const len = Math.floor(Math.log2(n));
    writer.writeUnary(len);
    const remainder = n - (1 << len);
    writer.writeBits(remainder, len);
    return writer.getBitString();
  }

  // Elias Gamma Decode
  static decodeGamma(reader) {
    const len = reader.readUnary();
    if (len === null) return null;
    if (len === 0) return 1;
    const remainder = reader.readBits(len);
    return (1 << len) + remainder;
  }

  // Encode an array of positive integers
  static encodeArray(arr) {
    let bitStream = '';
    for (const num of arr) {
      bitStream += EliasCodec.encodeGamma(num);
    }
    return bitStream;
  }

  // Decode a bit stream into an array of integers
  static decodeArray(bitString, count) {
    const reader = new BitStreamReader(bitString);
    const result = [];
    for (let i = 0; i < count; i++) {
      const val = EliasCodec.decodeGamma(reader);
      if (val === null) break;
      result.push(val);
    }
    return result;
  }
}

module.exports = { EliasCodec, BitStreamWriter, BitStreamReader };
