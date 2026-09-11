/**
 * Multi-Agent Distributed Asynchronous Verifiable Secret Sharing (AVSS) Engine
 * Implements Feldman verifiable secret sharing over Schnorr prime group
 * (p = 1019, q = 509, g = 4) where order of g is prime q.
 */

class AVSSEngine {
  constructor(p = 1019, q = 509, g = 4) {
    this.p = p; // Group modulus
    this.q = q; // Field order (prime subgroup size)
    this.g = g; // Generator of order q in Z_p*
  }

  modQ(n) {
    return ((n % this.q) + this.q) % this.q;
  }

  modP(n) {
    return ((n % this.p) + this.p) % this.p;
  }

  modPow(base, exp, mod) {
    let res = 1;
    let b = base % mod;
    let e = exp;
    while (e > 0) {
      if (e & 1) res = (res * b) % mod;
      b = (b * b) % mod;
      e >>= 1;
    }
    return res;
  }

  // Create polynomial over Z_q: P(x) = secret + a1*x + a2*x^2 ... mod q
  createPolynomial(secret, degree) {
    const coeffs = [this.modQ(secret)];
    for (let i = 1; i <= degree; i++) {
      coeffs.push(Math.floor(Math.random() * (this.q - 1)) + 1);
    }
    return coeffs;
  }

  // Evaluate polynomial at x in Z_q
  evaluate(coeffs, x) {
    let result = 0;
    let xPow = 1;
    for (const c of coeffs) {
      result = this.modQ(result + c * xPow);
      xPow = this.modQ(xPow * x);
    }
    return result;
  }

  // Generate public Feldman commitments in Z_p*: C_j = g^(a_j) mod p
  computeCommitments(coeffs) {
    return coeffs.map(c => this.modPow(this.g, c, this.p));
  }

  // Verify share (x, s) against public commitments: g^s == prod(C_j^(x^j)) mod p
  verifyShare(x, share, commitments) {
    const left = this.modPow(this.g, share, this.p);
    let right = 1;
    let xPow = 1;

    for (const c of commitments) {
      const term = this.modPow(c, xPow, this.p);
      right = (right * term) % this.p;
      xPow = this.modQ(xPow * x);
    }

    return left === right;
  }

  // Lagrange interpolation in Z_q to reconstruct secret from t+1 shares
  reconstruct(shares) {
    let secret = 0;
    const k = shares.length;

    for (let i = 0; i < k; i++) {
      const [xi, yi] = shares[i];
      let num = 1;
      let den = 1;

      for (let j = 0; j < k; j++) {
        if (i !== j) {
          const [xj] = shares[j];
          num = this.modQ(num * (-xj));
          den = this.modQ(den * (xi - xj));
        }
      }

      // Modular inverse of den in Z_q by Fermat's Little Theorem (q is prime)
      const denInv = this.modPow(den, this.q - 2, this.q);
      const lagrange = this.modQ(num * denInv);
      secret = this.modQ(secret + yi * lagrange);
    }

    return secret;
  }
}

module.exports = { AVSSEngine };
