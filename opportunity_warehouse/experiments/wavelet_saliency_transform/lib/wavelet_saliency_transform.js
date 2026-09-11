/**
 * Multi-Resolution Token Hierarchical Saliency Wavelet Transform
 * Implements 1D Discrete Haar Wavelet Transform over token saliency sequences,
 * decomposing into low-frequency macro trends and high-frequency details.
 */

class WaveletSaliencyTransform {
  // Forward 1D Haar Wavelet Transform (padded to power of 2)
  static forward(signal) {
    let n = signal.length;
    let power = 1;
    while (power < n) power *= 2;

    const padded = [...signal];
    while (padded.length < power) padded.push(0);

    const approx = [];
    const detail = [];

    for (let i = 0; i < padded.length; i += 2) {
      const a = padded[i];
      const b = padded[i + 1];
      approx.push((a + b) / Math.SQRT2);
      detail.push((a - b) / Math.SQRT2);
    }

    return {
      originalLength: n,
      paddedLength: power,
      approx,
      detail
    };
  }

  // Inverse 1D Haar Wavelet Transform
  static inverse(approx, detail, originalLength) {
    const reconstructed = [];
    for (let i = 0; i < approx.length; i++) {
      const a = approx[i];
      const d = detail[i];
      reconstructed.push((a + d) / Math.SQRT2);
      reconstructed.push((a - d) / Math.SQRT2);
    }
    return reconstructed.slice(0, originalLength);
  }

  // Threshold compression: zero out details below threshold
  static compress(signal, threshold = 0.1) {
    const tf = WaveletSaliencyTransform.forward(signal);
    const filteredDetail = tf.detail.map(d => Math.abs(d) < threshold ? 0 : d);
    const nonZeroCount = filteredDetail.filter(d => d !== 0).length + tf.approx.length;

    return {
      transformed: { ...tf, detail: filteredDetail },
      sparsityRatio: 1 - (nonZeroCount / (tf.approx.length + tf.detail.length)),
      reconstructed: WaveletSaliencyTransform.inverse(tf.approx, filteredDetail, tf.originalLength)
    };
  }
}

module.exports = { WaveletSaliencyTransform };
