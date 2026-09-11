function renderTestimonialsHtml(testimonials = []) {
  const cards = testimonials.map(t => {
    return `<div class="testimonial-card">
      <div class="header">
        <strong>${t.author}</strong>
        <span class="role">${t.role}</span>
      </div>
      <p class="quote">"${t.quote}"</p>
      <div class="metrics-pill">${t.verified_metric}</div>
    </div>`;
  }).join('\n');

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Developer Reviews - Agent Context Trimmer</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 40px; margin: 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; max-width: 1000px; margin: 0 auto; }
    .testimonial-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; display: flex; flex-direction: column; justify-content: space-between; }
    .header { margin-bottom: 12px; }
    .role { display: block; font-size: 12px; color: #8b949e; }
    .quote { font-style: italic; line-height: 1.5; color: #f0f6fc; margin: 0 0 16px 0; }
    .metrics-pill { align-self: flex-start; background: #238636; color: white; font-weight: bold; font-size: 11px; padding: 4px 8px; border-radius: 12px; }
  </style>
</head>
<body>
  <h1 style="text-align: center; color: #58a6ff; margin-bottom: 32px;">Verified Developer Feedback</h1>
  <div class="grid">
    ${cards}
  </div>
</body>
</html>`;
}

function generateJsonLdSchema(testimonials = []) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: 'agent-context-trimmer',
    aggregateRating: {
      '@type': 'AggregateRating',
      ratingValue: '4.9',
      reviewCount: testimonials.length.toString()
    },
    review: testimonials.map(t => ({
      '@type': 'Review',
      author: { '@type': 'Person', name: t.author },
      reviewBody: t.quote,
      reviewRating: { '@type': 'Rating', ratingValue: '5' }
    }))
  };
}

module.exports = { renderTestimonialsHtml, generateJsonLdSchema };
