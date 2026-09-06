import io
import re
import json
import html
import csv
import base64
import hashlib
import zipfile
import tarfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from .models import (
    TransformationOptions, DossierOptions, DossierSection,
    TransformationDossier, ExportPackageManifest, ExportPackage,
    DossierFormat, DossierType, TransformationStyle
)


def compute_sha256(data: Union[str, bytes]) -> str:
    """Computes SHA-256 hex digest for a string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def anonymize_text(text: str, redact_names: bool = True) -> str:
    """Anonymizes PII (emails, mentions, phone numbers, IP addresses) in text."""
    if not text:
        return text
    # Anonymize email addresses
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    text = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
    # Anonymize phone numbers
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    text = re.sub(phone_pattern, "[REDACTED_PHONE]", text)
    # Anonymize IP addresses
    ip_pattern = r'\b\d{1,3}(?:\.\d{1,3}){3}\b'
    text = re.sub(ip_pattern, "[REDACTED_IP]", text)
    # Anonymize mentions if requested
    if redact_names:
        text = re.sub(r'@([a-zA-Z0-9_-]+)', r'@user_anon', text)
    return text


class ContentTransformer:
    """Zero-dependency content transformation engine."""

    @staticmethod
    def render_markdown(
        title: str,
        summary: str,
        sections: List[DossierSection],
        metadata: Dict[str, Any],
        options: TransformationOptions
    ) -> str:
        lines: List[str] = []

        # 1. Frontmatter
        if options.include_frontmatter:
            lines.append("---")
            lines.append(f'title: "{title}"')
            lines.append(f'dossier_type: "{options.dossier_type}"')
            lines.append(f'style: "{options.style}"')
            lines.append(f'generated_at: "{datetime.utcnow().isoformat()}"')
            if metadata.get("target_id"):
                lines.append(f'target_id: "{metadata["target_id"]}"')
            if metadata.get("author"):
                lines.append(f'author: "{metadata["author"]}"')
            lines.append('generator: "SocialPlatform Dossier Engine v2.0"')
            lines.append("---\n")

        # 2. Main Title & Summary
        lines.append(f"# {title}\n")
        if summary:
            lines.append(f"> **Executive Summary**: {summary}\n")

        # 3. Table of Contents
        if options.include_toc and len(sections) > 1:
            lines.append("## Table of Contents")
            for idx, s in enumerate(sections, 1):
                anchor = re.sub(r'[^a-zA-Z0-9_-]', '', s.title.lower().replace(' ', '-'))
                lines.append(f"{idx}. [{s.title}](#{anchor}) ({s.item_count} items)")
            lines.append("\n---\n")

        # 4. Sections
        for s in sections:
            lines.append(f"## {s.title}\n")
            if s.content:
                content = s.content
                if options.anonymize_pii:
                    content = anonymize_text(content)
                lines.append(content)
                lines.append("\n")
            else:
                lines.append("*No records present in this section.*\n")

        # 5. Metadata Footer
        if options.include_system_metadata:
            lines.append("---\n")
            lines.append("### Dossier Verification & Metadata")
            lines.append(f"- **Generated At**: `{datetime.utcnow().isoformat()}`")
            lines.append(f"- **Total Sections**: `{len(sections)}`")
            for k, v in metadata.items():
                if k not in ("target_id", "author"):
                    lines.append(f"- **{k.replace('_', ' ').title()}**: `{v}`")

        return "\n".join(lines)

    @staticmethod
    def render_html(
        title: str,
        summary: str,
        sections: List[DossierSection],
        metadata: Dict[str, Any],
        options: TransformationOptions
    ) -> str:
        safe_title = html.escape(title)
        safe_summary = html.escape(summary)
        
        css = """
        :root {
            --bg: #0f172a; --card-bg: #1e293b; --text: #f8fafc;
            --muted: #94a3b8; --accent: #38bdf8; --border: #334155;
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        @media (prefers-color-scheme: light) {
            :root {
                --bg: #f8fafc; --card-bg: #ffffff; --text: #0f172a;
                --muted: #64748b; --accent: #0284c7; --border: #e2e8f0;
            }
        }
        body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; margin: 0; padding: 2rem 1rem; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }
        h1 { margin: 0 0 0.5rem 0; color: var(--accent); }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; font-size: 0.8rem; border-radius: 4px; background: var(--border); color: var(--muted); margin-right: 0.5rem; }
        .summary-box { background: var(--card-bg); border-left: 4px solid var(--accent); padding: 1rem; border-radius: 4px; margin: 1.5rem 0; }
        .toc { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.5rem; margin: 1.5rem 0; }
        .toc ul { margin: 0.5rem 0 0 1.2rem; padding: 0; }
        .toc li { margin: 0.3rem 0; }
        .section-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .section-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 0.75rem; margin-bottom: 1rem; }
        .section-title { font-size: 1.25rem; margin: 0; font-weight: 600; }
        .item-pill { font-size: 0.8rem; background: var(--border); padding: 0.2rem 0.6rem; border-radius: 12px; }
        pre, code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        pre { background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 6px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; }
        .footer { font-size: 0.85rem; color: var(--muted); border-top: 1px solid var(--border); padding-top: 1.5rem; margin-top: 2rem; }
        """

        html_parts: List[str] = [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"UTF-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            f"  <title>{safe_title}</title>",
            f"  <style>{css}</style>",
            "</head>",
            "<body>",
            "  <div class=\"container\">",
            "    <header class=\"header\">",
            f"      <h1>{safe_title}</h1>",
            f"      <div><span class=\"badge\">Type: {html.escape(options.dossier_type)}</span><span class=\"badge\">Style: {html.escape(options.style)}</span><span class=\"badge\">Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span></div>",
        ]

        if safe_summary:
            html_parts.append(f"      <div class=\"summary-box\"><strong>Executive Summary:</strong> {safe_summary}</div>")
        html_parts.append("    </header>")

        # Table of Contents
        if options.include_toc and len(sections) > 1:
            html_parts.append("    <nav class=\"toc\">")
            html_parts.append("      <strong>Table of Contents</strong>")
            html_parts.append("      <ul>")
            for idx, s in enumerate(sections, 1):
                sec_id = f"sec_{idx}"
                html_parts.append(f"        <li><a href=\"#{sec_id}\">{html.escape(s.title)}</a> ({s.item_count} items)</li>")
            html_parts.append("      </ul>")
            html_parts.append("    </nav>")

        # Sections
        for idx, s in enumerate(sections, 1):
            sec_id = f"sec_{idx}"
            sec_title = html.escape(s.title)
            sec_content = s.content
            if options.anonymize_pii:
                sec_content = anonymize_text(sec_content)
            safe_content = html.escape(sec_content)

            html_parts.append(f"    <section id=\"{sec_id}\" class=\"section-card\">")
            html_parts.append("      <div class=\"section-header\">")
            html_parts.append(f"        <h2 class=\"section-title\">{sec_title}</h2>")
            html_parts.append(f"        <span class=\"item-pill\">{s.item_count} items</span>")
            html_parts.append("      </div>")
            html_parts.append(f"      <div><pre>{safe_content}</pre></div>")
            html_parts.append("    </section>")

        # Footer
        html_parts.append("    <footer class=\"footer\">")
        html_parts.append("      <p>SocialPlatform Export & Dossier Packaging Engine v2.0 • Deterministic Verification</p>")
        html_parts.append("    </footer>")
        html_parts.append("  </div>")
        html_parts.append("</body>")
        html_parts.append("</html>")

        return "\n".join(html_parts)

    @staticmethod
    def render_text(
        title: str,
        summary: str,
        sections: List[DossierSection],
        metadata: Dict[str, Any],
        options: TransformationOptions
    ) -> str:
        lines: List[str] = []
        width = 80
        divider = "=" * width
        sub_divider = "-" * width

        lines.append(divider)
        lines.append(f" {title.upper()} ".center(width, "="))
        lines.append(divider)
        lines.append(f"Dossier Type : {options.dossier_type}")
        lines.append(f"Style        : {options.style}")
        lines.append(f"Generated At : {datetime.utcnow().isoformat()}")
        if metadata.get("target_id"):
            lines.append(f"Target ID    : {metadata['target_id']}")
        lines.append(divider)
        lines.append("")

        if summary:
            lines.append("SUMMARY:")
            lines.append(f"  {summary}")
            lines.append("")

        if options.include_toc and len(sections) > 1:
            lines.append("TABLE OF CONTENTS:")
            for idx, s in enumerate(sections, 1):
                lines.append(f"  [{idx}] {s.title} ({s.item_count} items)")
            lines.append("")
            lines.append(sub_divider)
            lines.append("")

        for idx, s in enumerate(sections, 1):
            lines.append(f"SECTION {idx}: {s.title.upper()} [{s.item_count} items]")
            lines.append(sub_divider)
            content = s.content
            if options.anonymize_pii:
                content = anonymize_text(content)
            lines.append(content)
            lines.append("")

        if options.include_system_metadata:
            lines.append(divider)
            lines.append("VERIFICATION & AUDIT LOG:")
            for k, v in metadata.items():
                lines.append(f"  {k}: {v}")
            lines.append(divider)

        return "\n".join(lines)

    @staticmethod
    def render_json(
        title: str,
        summary: str,
        sections: List[DossierSection],
        metadata: Dict[str, Any],
        options: TransformationOptions
    ) -> str:
        data = {
            "title": title,
            "summary": summary,
            "dossier_type": options.dossier_type,
            "style": options.style,
            "options": options.to_dict(),
            "generated_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
            "sections": [
                {
                    "title": s.title,
                    "section_type": s.section_type,
                    "item_count": s.item_count,
                    "content": anonymize_text(s.content) if options.anonymize_pii else s.content,
                    "metadata": s.metadata
                }
                for s in sections
            ]
        }
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def render_csv(
        sections: List[DossierSection],
        metadata: Dict[str, Any],
        options: TransformationOptions
    ) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Section Title", "Section Type", "Item Count", "Content Snippet", "Metadata"])
        for s in sections:
            content = anonymize_text(s.content) if options.anonymize_pii else s.content
            snippet = content.replace("\n", " ")[:200]
            writer.writerow([s.title, s.section_type, s.item_count, snippet, json.dumps(s.metadata, default=str)])
        return output.getvalue()


def build_dossier_from_sections(
    target_id: str,
    target_type: str,
    title: str,
    dossier_type: str,
    format_type: str,
    summary: str,
    sections: List[DossierSection],
    item_counts: Dict[str, int],
    metadata: Dict[str, Any],
    options: Optional[TransformationOptions] = None
) -> TransformationDossier:
    """Builds and formats a TransformationDossier with checksums and rendered content."""
    opts = options or TransformationOptions(format=format_type, dossier_type=dossier_type)
    opts.format = format_type
    opts.dossier_type = dossier_type

    # Format the content
    fmt = format_type.lower().strip().lstrip(".")
    if fmt in ("markdown", "md"):
        rendered = ContentTransformer.render_markdown(title, summary, sections, metadata, opts)
    elif fmt == "html":
        rendered = ContentTransformer.render_html(title, summary, sections, metadata, opts)
    elif fmt in ("text", "txt"):
        rendered = ContentTransformer.render_text(title, summary, sections, metadata, opts)
    elif fmt == "csv":
        rendered = ContentTransformer.render_csv(sections, metadata, opts)
    elif fmt == "json":
        rendered = ContentTransformer.render_json(title, summary, sections, metadata, opts)
    else:
        rendered = ContentTransformer.render_markdown(title, summary, sections, metadata, opts)

    checksum = compute_sha256(rendered)
    dossier_id = f"dos_{uuid.uuid4().hex[:12]}"

    return TransformationDossier(
        id=dossier_id,
        title=title,
        dossier_type=dossier_type,
        format=format_type,
        target_id=target_id,
        target_type=target_type,
        summary=summary,
        sections=sections,
        rendered_content=rendered,
        item_counts=item_counts,
        checksum=checksum,
        size_bytes=len(rendered.encode("utf-8")),
        created_at=datetime.utcnow(),
        metadata=metadata
    )


def package_archive(
    user_id: str,
    files: Dict[str, Union[str, bytes]],
    format_type: str = "zip",
    metadata: Optional[Dict[str, Any]] = None
) -> ExportPackage:
    """Packages multiple dossier files and data bundles into a ZIP or TAR archive."""
    format_norm = format_type.lower().strip().lstrip(".")
    pkg_id = f"pkg_{uuid.uuid4().hex[:12]}"
    created_now = datetime.utcnow()
    meta = metadata or {}

    manifest_files = []
    total_bytes = 0

    all_files: Dict[str, Union[str, bytes]] = dict(files)
    for fname, content in list(all_files.items()):
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        f_hash = compute_sha256(content_bytes)
        f_size = len(content_bytes)
        total_bytes += f_size
        manifest_files.append({
            "path": fname,
            "size_bytes": f_size,
            "checksum": f_hash,
            "content_type": "application/json" if fname.endswith(".json") else "text/markdown" if fname.endswith(".md") else "text/html" if fname.endswith(".html") else "text/plain"
        })

    manifest_dict = {
        "package_id": pkg_id,
        "user_id": user_id,
        "format": format_norm,
        "total_files": len(manifest_files) + 1,
        "total_bytes": total_bytes,
        "created_at": created_now.isoformat(),
        "files": manifest_files,
        "metadata": meta
    }
    manifest_bytes = json.dumps(manifest_dict, indent=2).encode("utf-8")
    all_files["manifest.json"] = manifest_bytes

    if format_norm in ("tar", "tar.gz"):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz" if format_norm == "tar.gz" else "w") as tar:
            for filename, content in all_files.items():
                content_bytes = content.encode("utf-8") if isinstance(content, str) else content
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(content_bytes)
                tarinfo.mtime = int(created_now.timestamp())
                tar.addfile(tarinfo, io.BytesIO(content_bytes))
        archive_bytes = buffer.getvalue()
        ext = "tar.gz" if format_norm == "tar.gz" else "tar"
        content_type = "application/x-tar"
    else:
        # Default to ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in all_files.items():
                content_bytes = content.encode("utf-8") if isinstance(content, str) else content
                zf.writestr(filename, content_bytes)
        archive_bytes = buffer.getvalue()
        ext = "zip"
        content_type = "application/zip"

    pkg_checksum = compute_sha256(archive_bytes)
    b64_str = base64.b64encode(archive_bytes).decode("ascii")

    manifest = ExportPackageManifest(
        package_id=pkg_id,
        user_id=user_id,
        format=ext,
        file_list=manifest_files,
        total_files=len(all_files),
        total_bytes=len(archive_bytes),
        checksum=pkg_checksum,
        created_at=created_now,
        metadata=meta
    )

    return ExportPackage(
        manifest=manifest,
        archive_bytes=archive_bytes,
        archive_base64=b64_str,
        filename=f"user_export_{user_id}_{created_now.strftime('%Y%m%d_%H%M%S')}.{ext}",
        content_type=content_type
    )
