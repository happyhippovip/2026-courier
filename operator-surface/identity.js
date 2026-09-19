fetch('/test-build-identity.json').then(r=>r.json()).then(id => {
  let div = document.createElement('div');
  div.className = 'build-identity';
  div.innerHTML = `
    <strong>Courier Symphony TEST BUILD</strong><br>
    Branch: ${id.branch}<br>
    Commit: ${id.commit_sha}<br>
    Tree: ${id.tree_sha}<br>
    OS: ${id.os}<br>
    Built: ${id.built_at}<br>
    Smoke: ${id.smoke_result}<br>
    <span class="badge">SAME CANDIDATE</span>
  `;
  document.body.prepend(div);
}).catch(e => console.log("No build identity found"));
