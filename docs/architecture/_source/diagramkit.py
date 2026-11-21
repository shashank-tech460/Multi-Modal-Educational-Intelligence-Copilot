"""Tiny, dependency-free SVG toolkit for the EduCopilot architecture diagrams.

Every diagram body is drawn in a fixed 1600 x 860 coordinate space and then placed into
two layouts:
  * documentation layout  (1700 px wide, title + diagram + legend + technical notes)
  * presentation layout   (1920 x 1080, 16:9, larger title, compact legend, no notes)

Only the Python standard library is used. Run build_diagrams.py to regenerate all SVGs.
"""
from __future__ import annotations

from html import escape

FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "Consolas, 'SFMono-Regular', Menlo, monospace"

# ---------------------------------------------------------------- design system
PALETTE = {
    "app":     {"fill": "#EFF6FF", "stroke": "#2563EB", "text": "#1E3A8A"},   # Team 4C application
    "auth":    {"fill": "#F5F3FF", "stroke": "#7C3AED", "text": "#4C1D95"},   # Team 4C auth + integration layer
    "core":    {"fill": "#ECFDF5", "stroke": "#059669", "text": "#064E3B"},   # Team 4A/4B capabilities
    "store":   {"fill": "#FFFBEB", "stroke": "#D97706", "text": "#78350F"},   # data stores
    "ext":     {"fill": "#F8FAFC", "stroke": "#64748B", "text": "#1E293B"},   # external / runtime / user
    "warn":    {"fill": "#FEF2F2", "stroke": "#DC2626", "text": "#7F1D1D"},   # refusal / trust boundary
    "neutral": {"fill": "#FFFFFF", "stroke": "#94A3B8", "text": "#0F172A"},
}
INK = "#334155"
MUTED = "#64748B"
BOUNDARY = "#DC2626"

LEGEND_ITEMS = [
    ("app", "Team 4C application (Next.js)"),
    ("auth", "Team 4C authentication and integration layer"),
    ("core", "Team 4A/4B capabilities (joint FastAPI backend)"),
    ("store", "Data store"),
    ("ext", "User, runtime or external service"),
]


def _wrap(text: str, max_chars: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines


class Canvas:
    """Collects SVG elements for one diagram body (1600 x 860)."""

    W, H = 1600, 860

    def __init__(self) -> None:
        self.el: list[str] = []
        self.warnings: list[str] = []

    # ------------------------------------------------------------ primitives
    def text(self, x, y, s, size=13, weight="400", color=INK, anchor="start", family=FONT, italic=False):
        style = ' font-style="italic"' if italic else ""
        self.el.append(
            f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}"{style}>{escape(s)}</text>')

    def box(self, x, y, w, h, title, body="", kind="neutral", title_size=15, body_size=12.5, mono_title=False,
            radius=10, dashed=False):
        p = PALETTE[kind]
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{p["fill"]}" '
                       f'stroke="{p["stroke"]}" stroke-width="1.6"{dash}/>')
        lines_t = _wrap(title, int((w - 18) / (title_size * 0.52)))
        lines_b = []
        for para in body.split("\n") if body else []:
            lines_b += _wrap(para, int((w - 18) / (body_size * 0.5))) if para else [""]
        total = len(lines_t) * (title_size + 4) + len(lines_b) * (body_size + 4.5) + (6 if lines_b else 0)
        if total > h - 10:
            self.warnings.append(f"text overflow in box '{title}' ({total:.0f}px > {h - 10}px)")
        cy = y + (h - total) / 2 + title_size
        for ln in lines_t:
            self.text(x + w / 2, cy, ln, size=title_size, weight="600", color=p["text"], anchor="middle",
                      family=MONO if mono_title else FONT)
            cy += title_size + 4
        cy += 6 - 4 + body_size * 0.2
        for ln in lines_b:
            self.text(x + w / 2, cy + body_size * 0.6, ln, size=body_size, color=INK, anchor="middle")
            cy += body_size + 4.5

    def cylinder(self, x, y, w, h, title, body="", kind="store", title_size=15, body_size=12.5):
        p = PALETTE[kind]
        e = 9
        self.el.append(
            f'<path d="M{x},{y + e} a{w / 2},{e} 0 0,0 {w},0 v{h - 2 * e} a{w / 2},{e} 0 0,1 {-w},0 z" '
            f'fill="{p["fill"]}" stroke="{p["stroke"]}" stroke-width="1.6"/>')
        self.el.append(f'<ellipse cx="{x + w / 2}" cy="{y + e}" rx="{w / 2}" ry="{e}" fill="{p["fill"]}" '
                       f'stroke="{p["stroke"]}" stroke-width="1.6"/>')
        # reuse box text layout without a frame
        before = len(self.el)
        self.box(x, y + 2 * e, w, h - 2 * e, title, body, kind, title_size, body_size)
        self.el.pop(before)  # drop the rect drawn by box()

    def group(self, x, y, w, h, label, kind="neutral", sublabel="", dashed=True, label_size=14, label_x=None):
        p = PALETTE[kind]
        dash = ' stroke-dasharray="8 5"' if dashed else ""
        fill = p["fill"] if kind != "neutral" else "#FFFFFF"
        self.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" fill-opacity="0.45" '
                       f'stroke="{p["stroke"]}" stroke-width="1.8"{dash}/>')
        self.text(label_x if label_x is not None else x + 14, y + 22, label, size=label_size, weight="700", color=p["text"])
        if sublabel:
            self.text(x + 14, y + 40, sublabel, size=12, color=MUTED)

    def boundary_line(self, x1, y1, x2, y2, label, lx, ly, anchor="start"):
        self.el.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{BOUNDARY}" stroke-width="2.4" '
                       f'stroke-dasharray="10 6"/>')
        self.label(lx, ly, label, color=BOUNDARY, weight="700", size=13, anchor=anchor)

    def label(self, x, y, s, size=12, color=INK, weight="400", anchor="start", bg=True):
        if bg:
            w = len(s) * size * 0.5 + 8
            bx = x - 4 if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w + 4)
            self.el.append(f'<rect x="{bx:.1f}" y="{y - size - 1}" width="{w:.1f}" height="{size + 6}" rx="3" '
                           f'fill="#FFFFFF" fill-opacity="0.92"/>')
        self.text(x, y, s, size=size, weight=weight, color=color, anchor=anchor)

    def badge(self, x, y, n, color="#0F172A"):
        self.el.append(f'<circle cx="{x}" cy="{y}" r="11.5" fill="{color}" stroke="#FFFFFF" stroke-width="2"/>')
        self.text(x, y + 4.5, str(n), size=12.5, weight="700", color="#FFFFFF", anchor="middle")

    def arrow(self, pts, color=INK, dashed=False, both=False, width=1.8):
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        start = ' marker-start="url(#arrowStart)"' if both else ""
        mid = color.replace("#", "")
        self.el.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash} '
                       f'marker-end="url(#arrow_{mid})"{start} stroke-linejoin="round"/>')
        _MARKER_COLORS.add(color)

    def note(self, x, y, lines, size=12, color=MUTED):
        for i, ln in enumerate(lines):
            self.text(x, y + i * (size + 5), ln, size=size, color=color)

    def svg_body(self) -> str:
        return "\n".join(self.el)


_MARKER_COLORS: set[str] = {INK}


def _defs() -> str:
    out = ["<defs>"]
    for c in sorted(_MARKER_COLORS):
        cid = c.replace("#", "")
        out.append(f'<marker id="arrow_{cid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
                   f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    out.append(f'<marker id="arrowStart" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="8" markerHeight="8" '
               f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>')
    out.append("</defs>")
    return "\n".join(out)


def _legend(x, y, extra_lines, horizontal=False, size=13, x_max=None):
    el = []
    items = list(LEGEND_ITEMS)
    if horizontal:
        cx, cy = x, y
        entries = [(k, l) for k, l in items] + [("line:" + k, l) for k, l in extra_lines]
        for kind, label in entries:
            width = 44 + len(label) * size * 0.53
            if x_max and cx + width > x_max:
                cx, cy = x, cy + 30
            if kind.startswith("line:"):
                el += _legend_line(cx, cy, kind[5:], label, size)
            else:
                p = PALETTE[kind]
                el.append(f'<rect x="{cx}" y="{cy - 13}" width="22" height="16" rx="4" fill="{p["fill"]}" stroke="{p["stroke"]}" stroke-width="1.6"/>')
                el.append(f'<text x="{cx + 30}" y="{cy}" font-family="{FONT}" font-size="{size}" fill="{INK}">{escape(label)}</text>')
            cx += width + 18
        return "\n".join(el)
    for i, (kind, label) in enumerate(items):
        p = PALETTE[kind]
        yy = y + i * 26
        el.append(f'<rect x="{x}" y="{yy - 13}" width="22" height="16" rx="4" fill="{p["fill"]}" stroke="{p["stroke"]}" stroke-width="1.6"/>')
        el.append(f'<text x="{x + 32}" y="{yy}" font-family="{FONT}" font-size="{size}" fill="{INK}">{escape(label)}</text>')
    for j, (kind, label) in enumerate(extra_lines):
        el += _legend_line(x, y + (len(items) + j) * 26, kind, label, size)
    return "\n".join(el)


def _legend_line(x, y, kind, label, size):
    el = []
    if kind == "flow":
        el.append(f'<line x1="{x}" y1="{y - 5}" x2="{x + 22}" y2="{y - 5}" stroke="{INK}" stroke-width="1.8" marker-end="url(#arrow_{INK[1:]})"/>')
    elif kind == "both":
        el.append(f'<line x1="{x + 2}" y1="{y - 5}" x2="{x + 22}" y2="{y - 5}" stroke="{INK}" stroke-width="1.8" marker-start="url(#arrowStart)" marker-end="url(#arrow_{INK[1:]})"/>')
    elif kind == "return":
        el.append(f'<line x1="{x}" y1="{y - 5}" x2="{x + 22}" y2="{y - 5}" stroke="{INK}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#arrow_{INK[1:]})"/>')
    elif kind == "boundary":
        el.append(f'<line x1="{x}" y1="{y - 5}" x2="{x + 22}" y2="{y - 5}" stroke="{BOUNDARY}" stroke-width="2.4" stroke-dasharray="6 4"/>')
    elif kind == "badge":
        el.append(f'<circle cx="{x + 11}" cy="{y - 5}" r="10" fill="#0F172A"/>'
                  f'<text x="{x + 11}" y="{y - 1}" font-family="{FONT}" font-size="11" font-weight="700" fill="#fff" text-anchor="middle">1</text>')
    el.append(f'<text x="{x + 32}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{INK}">{escape(label)}</text>')
    return el


FOOTER = ("EduCopilot — Multi-Modal Educational Intelligence Copilot · Accion Labs industry project (2026) · "
          "verified final integrated build, local demo configuration (not a production deployment)")


def documentation_svg(canvas: Canvas, title: str, subtitle: str, notes: list[str], legend_extra) -> str:
    W = 1700
    body_y = 112
    panel_y = body_y + Canvas.H + 34
    n_leg = len(LEGEND_ITEMS) + len(legend_extra)
    note_lines = []
    for n in notes:
        note_lines += [("• " if i == 0 else "  ") + ln for i, ln in enumerate(_wrap(n, 108))]
    panel_h = max(n_leg * 26 + 60, len(note_lines) * 19 + 60)
    H = panel_y + panel_h + 56
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'role="img" aria-label="{escape(title)}">', _defs(),
             f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
             f'<rect x="0" y="0" width="{W}" height="6" fill="#2563EB"/>',
             f'<rect x="{W / 3:.0f}" y="0" width="{W / 3:.0f}" height="6" fill="#7C3AED"/>',
             f'<rect x="{2 * W / 3:.0f}" y="0" width="{W / 3:.0f}" height="6" fill="#059669"/>',
             f'<text x="50" y="58" font-family="{FONT}" font-size="30" font-weight="700" fill="#0F172A">{escape(title)}</text>',
             f'<text x="50" y="90" font-family="{FONT}" font-size="15.5" fill="{MUTED}">{escape(subtitle)}</text>',
             f'<g transform="translate(50,{body_y})">', canvas.svg_body(), "</g>",
             f'<rect x="50" y="{panel_y}" width="{W - 100}" height="{panel_h}" rx="12" fill="#F8FAFC" stroke="#E2E8F0"/>',
             f'<text x="74" y="{panel_y + 32}" font-family="{FONT}" font-size="15" font-weight="700" fill="#0F172A">Legend</text>',
             _legend(74, panel_y + 62, legend_extra),
             f'<text x="560" y="{panel_y + 32}" font-family="{FONT}" font-size="15" font-weight="700" fill="#0F172A">Technical notes</text>']
    for i, ln in enumerate(note_lines):
        parts.append(f'<text x="560" y="{panel_y + 60 + i * 19}" font-family="{FONT}" font-size="13" fill="{INK}">{escape(ln)}</text>')
    parts.append(f'<text x="50" y="{H - 24}" font-family="{FONT}" font-size="12" fill="{MUTED}">{escape(FOOTER)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def presentation_svg(canvas: Canvas, title: str, tagline: str, legend_extra) -> str:
    W, H = 1920, 1080
    top, bottom = 118, 112
    scale = min((W - 80) / Canvas.W, (H - top - bottom) / Canvas.H)
    bw = Canvas.W * scale
    bx = (W - bw) / 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'role="img" aria-label="{escape(title)}">', _defs(),
             f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
             f'<rect x="0" y="0" width="{W}" height="104" fill="#0F172A"/>',
             f'<rect x="0" y="104" width="{W / 3:.0f}" height="5" fill="#2563EB"/>',
             f'<rect x="{W / 3:.0f}" y="104" width="{W / 3:.0f}" height="5" fill="#7C3AED"/>',
             f'<rect x="{2 * W / 3:.0f}" y="104" width="{W / 3:.0f}" height="5" fill="#059669"/>',
             f'<text x="56" y="62" font-family="{FONT}" font-size="38" font-weight="700" fill="#FFFFFF">{escape(title)}</text>',
             f'<text x="56" y="90" font-family="{FONT}" font-size="17" fill="#CBD5E1">{escape(tagline)}</text>',
             f'<text x="{W - 56}" y="62" font-family="{FONT}" font-size="17" fill="#CBD5E1" text-anchor="end">EduCopilot · Accion Labs · 2026</text>',
             f'<g transform="translate({bx:.1f},{top}) scale({scale:.4f})">', canvas.svg_body(), "</g>",
             f'<line x1="56" y1="{H - 96}" x2="{W - 56}" y2="{H - 96}" stroke="#E2E8F0"/>',
             _legend(56, H - 62, legend_extra, horizontal=True, size=15, x_max=W - 56),
             "</svg>"]
    return "\n".join(parts)
