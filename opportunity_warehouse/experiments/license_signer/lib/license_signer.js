const crypto = require('crypto');

function generateKeyPair() {
  return crypto.generateKeyPairSync('ec', {
    namedCurve: 'prime256v1',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
  });
}

function signLicense(payload, privateKeyPem) {
  const dataString = JSON.stringify(payload);
  const signer = crypto.createSign('SHA256');
  signer.update(dataString);
  signer.end();
  const signature = signer.sign(privateKeyPem, 'base64');

  return {
    payload,
    signature,
    signed_at: new Date().toISOString()
  };
}

function verifyLicense(signedToken, publicKeyPem) {
  try {
    const dataString = JSON.stringify(signedToken.payload);
    const verifier = crypto.createVerify('SHA256');
    verifier.update(dataString);
    verifier.end();
    const isValid = verifier.verify(publicKeyPem, signedToken.signature, 'base64');
    return {
      is_valid: isValid,
      payload: signedToken.payload
    };
  } catch (err) {
    return {
      is_valid: false,
      error: err.message
    };
  }
}

module.exports = { generateKeyPair, signLicense, verifyLicense };
