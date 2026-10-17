"""Offline text reports. All document text is escaped; no remote images or scripts."""

import html
import re
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextDocument,
)

from qma_face import __version__
from qma_face.core.i18n import tr


def paragraphs(text: str) -> str:
    result = []
    for line in text.splitlines():
        if not line.strip():
            result.append('<p style="font-size:3px;margin:0">&#160;</p>')
            continue
        direction = (
            ' dir="rtl" style="text-align:right;direction:rtl"'
            if re.search(r"[\u0600-\u06ff]", line)
            else ' dir="ltr"'
        )
        result.append(f"<p{direction}>{html.escape(line) or '&#160;'}</p>")
    return "".join(result)


def report_html(
    text: str,
    *,
    language: str,
    engine_hash: str | None = None,
    sources: list[dict] | None = None,
    include_excerpts: bool = False,
    summary: bool = False,
) -> str:
    def t(key):
        return tr(key, language)

    sources = sources or []
    source_sections = []
    for source in sources:
        locator = (
            f"p. {source['page']}"
            if source.get("page")
            else source.get("doi", source.get("url", ""))
        )
        source_sections.append(
            paragraphs(
                f"[{source.get('citation_id', '—')}] {source.get('title', '')} · {locator} · "
                f"{source.get('type', '')}"
            )
        )
        if include_excerpts and not summary:
            source_sections.append(paragraphs(str(source.get("text", ""))[:6000]))
    if summary:
        # A visibly labeled excerpt; full result and source text remain in PDF/HTML.
        text = "\n".join(text.splitlines()[:14])
    model = "QMA Face Engine research v1 · " + (engine_hash or "—")
    model += "\nQwen3-VL-4B-Instruct Q4_K_M · chat; not necessarily invoked for this result"
    if language == "fr":
        model = model.replace(
            "chat; not necessarily invoked for this result",
            "chat ; pas nécessairement invoqué pour ce résultat",
        )
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    return (
        '<!doctype html><html lang="' + language + '"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>QMA Face</title><style>"
        'body{font-family:"Segoe UI",sans-serif;color:#29263e;background:#fff;'
        "max-width:900px;margin:38px auto;padding:24px;line-height:1.4}"
        "h1{color:#7566bd;font-size:25px}h2{color:#7566bd;font-size:17px;margin-top:22px}"
        "p{margin:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}"
        ".note{background:#f1edfa;padding:14px;border-radius:10px}"
        ".small{font-size:11px;color:#69637d} @media print{body{margin:0;padding:0;max-width:none}}"
        "</style></head><body>"
        f"<h1>{html.escape(t('report_title'))}{' · ' + t('summary_label') if summary else ''}</h1>"
        f'<p class="small">v{__version__} · {stamp} · {language.upper()}</p>'
        f'<div class="note">{paragraphs(t("report_limits"))}</div>'
        "<h2>"
        + html.escape(t("model_label"))
        + "</h2>"
        + paragraphs(model)
        + "<h2>"
        + html.escape(t("result_label"))
        + "</h2>"
        + paragraphs(text)
        + "<h2>"
        + html.escape(t("sources_label"))
        + "</h2>"
        + ("".join(source_sections) or paragraphs(t("no_sources")))
        + '<p class="small">'
        + html.escape(t("report_private"))
        + "</p></body></html>"
    )


def document(markup: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setDefaultFont(QFont("Segoe UI", 10))
    doc.setDocumentMargin(12)
    doc.setHtml(markup.replace("</style>", "body{margin:0;padding:0}p{margin:4px 0}</style>"))
    return doc


def export_report(
    path: Path, text: str, *, language: str, engine_hash=None, sources=None, include_excerpts=False
) -> None:
    suffix = path.suffix.lower()
    if suffix not in {".html", ".pdf", ".png"}:
        raise ValueError("Choose PDF, HTML or PNG")
    markup = report_html(
        text,
        language=language,
        engine_hash=engine_hash,
        sources=sources,
        include_excerpts=include_excerpts,
        summary=suffix == ".png",
    )
    if suffix == ".html":
        path.write_text(markup, encoding="utf-8")
        return
    doc = document(markup)
    if suffix == ".pdf":
        writer = QPdfWriter(str(path))
        writer.setTitle("QMA Face · research report")
        writer.setCreator(f"QMA Face {__version__}")
        writer.setResolution(144)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(16, 16, 16, 16), QPageLayout.Unit.Millimeter)
        doc.print_(writer)
        del writer
        if not path.is_file() or path.stat().st_size < 100:
            raise OSError("PDF export failed")
    else:
        doc.setPageSize(QSizeF(1000, -1))
        doc.setTextWidth(1000)
        height = int(doc.size().height()) + 48
        if height > 16000:
            raise ValueError("Summary is too long; export PDF instead")
        image = QImage(1048, height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#F8F6FE"))
        painter = QPainter(image)
        painter.translate(24, 24)
        doc.drawContents(painter)
        painter.end()
        if not image.save(str(path), "PNG"):
            raise OSError("PNG export failed")
