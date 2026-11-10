#!/usr/bin/env python3
"""Build the profile README panels in the mujahidk.com editorial style.

GitHub READMEs cannot load custom CSS or web fonts, so each section of the site
is rendered as a self-contained SVG with the fonts it uses subset and embedded.
Every panel except the hero comes in a light and a dark variant; the README
switches between them with <picture> and prefers-color-scheme.

Usage:  .venv/bin/python scripts/build.py
Edit CONTENT below when the website changes, then rebuild and commit.
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
OUT = ROOT / "assets"
SITE = "https://mujahidk.com"
W = 880  # canvas width; panels render at 100% of the README column

# ─── Content (mirrors mujahidk.com) ──────────────────────────────────────────

CONTENT = {
    "eyebrow": "DevOps & cloud platform leadership / Healthcare technology",
    "name": ["Mujahid", "Khaleel"],
    "facts": [
        ("20+", "Years in software engineering"),
        ("AWS", "Cloud platform engineering"),
        ("HIPAA & SOC 2", "Compliance in healthcare technology"),
    ],
    "intro": "Sr. Director, DevOps, leading platform engineering, cloud and security for healthcare technology.",
    "intro_sub": "Rooted in software development: 20+ years writing and shipping code across the stack. Leadership that stays close to the work.",
    "mission": "I lead the DevOps and Cloud Platform teams that keep healthcare products secure, compliant and available, turning manual, ticket-driven work into automated platforms, with security and AI-driven automation built in.",
    "stack": [
        "AWS", "Kubernetes", "Terraform", "Docker", "Jenkins", "GitHub Actions",
        "Python", "Java", "JavaScript", "Linux", "Bash", "Ansible", "Grafana",
        "CircleCI", "Dynatrace", "Sumo Logic",
    ],
    "focus": [
        ("cloud", "/cloud/", "Cloud foundations",
         "From migration planning to day-two operations, I focus on resilient AWS architectures, practical security controls, and operating models that teams can sustain over time.",
         "AWS / IaC / Security / Well-Architected"),
        ("programming", "/programming/", "Programming",
         "I use code as the interface for delivery and operations, combining application development, infrastructure automation, and scripting to eliminate manual bottlenecks.",
         "Java / Python / JavaScript / Bash"),
        ("cicd", "/cicd/", "CI/CD",
         "My work centers on reliable pipelines, paved-road developer workflows, and release processes that balance speed, traceability, and compliance.",
         "Jenkins / GitHub Actions / CircleCI / Kubernetes"),
    ],
    "cases": [
        ("liquibase", "/case-studies/liquibase-introduction/",
         "Liquibase Introduction and Implementation",
         "Database change management and version control", None),
        ("logging", "/case-studies/logging-and-observability/",
         "Logging, MDC, Trace ID and Log Aggregator",
         "Distributed tracing and centralized log aggregation", None),
        ("vendor-api", "/case-studies/vendor-api-simulator/",
         "Vendor API Simulator",
         "Template-driven vendor APIs for PHI-free development, testing and demos", None),
    ],
    "sign_line": "Leadership that stays close to the work.",
}

# ─── Palette (editorial.scss tokens; dark is an adaptation for GitHub dark) ──

ACCENT = "#0047FF"
THEMES = {
    "light": dict(ink="#202220", muted="#656963", line="#DCDED7", accent=ACCENT,
                  band="#202220", band_ink="#F8F7F3", btn="#F8F7F3", btn_ink="#202220"),
    "dark": dict(ink="#F0EFEA", muted="#9DA19A", line="#3A3D38", accent="#5C8DFF",
                 band="#F8F7F3", band_ink="#202220", btn="#202220", btn_ink="#F8F7F3"),
}

# ─── Fonts ───────────────────────────────────────────────────────────────────

FAMILIES = {"sans": "HankenGrotesk.ttf", "serif": "Fraunces-Italic.ttf"}


@lru_cache(maxsize=None)
def static_font(family: str, weight: int) -> TTFont:
    font = TTFont(FONTS / FAMILIES[family])
    axes = {"wght": weight}
    if family == "serif":
        axes.update(opsz=144, SOFT=0, WONK=0)
    return instancer.instantiateVariableFont(font, axes)


def text_width(text: str, family: str, weight: int, size: float, ls: float = 0) -> float:
    font = static_font(family, weight)
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    upm = font["head"].unitsPerEm
    adv = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text)
    return adv * size / upm + ls * size * len(text)


def wrap(text: str, family: str, weight: int, size: float, max_w: float, ls: float = 0) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and text_width(trial, family, weight, size, ls) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def font_face(family: str, weight: int, chars: str) -> str:
    font = static_font(family, weight)
    buf = io.BytesIO()
    font.save(buf)
    buf.seek(0)
    sub = TTFont(buf)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    opts.notdef_outline = True
    s = subset.Subsetter(opts)
    s.populate(text=chars + " ")
    s.subset(sub)
    out = io.BytesIO()
    sub.flavor = "woff2"
    sub.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}{weight}';"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")


# ─── SVG builder ─────────────────────────────────────────────────────────────

class Svg:
    def __init__(self):
        self.parts: list[str] = []
        self.used: dict[tuple[str, int], set[str]] = {}

    def rect(self, x, y, w, h, fill, opacity=1):
        op = f' fill-opacity="{opacity}"' if opacity != 1 else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"{op}/>')

    def line(self, x1, y, x2, color, opacity=1):
        self.rect(x1, y, x2 - x1, 1, color, opacity)

    def text(self, x, y, s, family, weight, size, fill, ls=0, anchor="start", upper=False, opacity=1):
        s = s.upper() if upper else s
        self.used.setdefault((family, weight), set()).update(s)
        attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f"font-family=\"'{family}{weight}'\"",
                 f'font-size="{size}"', f'fill="{fill}"']
        if ls:
            attrs.append(f'letter-spacing="{ls * size:.2f}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if opacity != 1:
            attrs.append(f'fill-opacity="{opacity}"')
        self.parts.append(f'<text {" ".join(attrs)}>{escape(s)}</text>')

    def arrow(self, x, y, color, size=18):
        k = size / 20
        self.parts.append(
            f'<path transform="translate({x:.1f} {y:.1f}) scale({k:.3f})" d="M3 10h14M11 4l6 6-6 6" '
            f'fill="none" stroke="{color}" stroke-width="1.5"/>')

    def render(self, height: float, title: str) -> str:
        faces = "".join(font_face(f, w, "".join(sorted(c))) for (f, w), c in sorted(self.used.items()))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height:.0f}" '
                f'viewBox="0 0 {W} {height:.0f}" role="img" aria-label="{escape(title)}">'
                f"<title>{escape(title)}</title><style>{faces}"
                f"text{{font-kerning:normal;text-rendering:geometricPrecision}}</style>"
                + "".join(self.parts) + "</svg>")


def save(name: str, svg: str):
    (OUT / f"{name}.svg").write_text(svg)
    print(f"  {name}.svg  {len(svg) / 1024:.1f} KB")


# ─── Panels ──────────────────────────────────────────────────────────────────

def hero() -> str:
    c, s, pad = CONTENT, Svg(), 44
    white = "#FFFFFF"
    y = 52
    s.text(pad, y, c["eyebrow"], "sans", 500, 12, white, ls=.07, upper=True)

    # Name block sized to fit beside the facts column
    facts_w = 236
    avail = W - pad * 2 - facts_w - 40
    names = [c["name"][0].upper(), c["name"][1].upper() + "."]
    size = 120
    while max(text_width(n, "sans", 900, size, -.06) for n in names) > avail:
        size -= 2
    top = y + 52
    base1 = top + size * .78
    base2 = base1 + size * .9
    s.text(pad - size * .03, base1, names[0], "sans", 900, size, white, ls=-.06)
    s.text(pad - size * .03, base2, names[1][:-1], "sans", 900, size, white, ls=-.06)
    dot_x = pad - size * .03 + text_width(names[1][:-1], "sans", 900, size, -.06) + size * .06
    s.text(dot_x, base2, ".", "sans", 900, size, white)
    name_bottom = base2

    # Facts, bottom-aligned with the name
    fx, row_h = W - pad - facts_w, 72
    fy = name_bottom - row_h * len(c["facts"]) + 6
    for dd, dt in c["facts"]:
        s.line(fx, fy, W - pad, white, .35)
        s.text(fx, fy + 14 + 26, dd, "sans", 850, 30, white, ls=-.04)
        s.text(fx, fy + 14 + 26 + 22, dt, "sans", 400, 13, white, opacity=.85)
        fy += row_h

    # Lede and call to action
    y = name_bottom + 64
    for ln in wrap(c["intro"], "sans", 400, 20, 440, -.015):
        y += 30
        s.text(pad, y, ln, "sans", 400, 20, white, ls=-.015)
    y += 10
    for ln in wrap(c["intro_sub"], "sans", 400, 16, 440):
        y += 24
        s.text(pad, y, ln, "sans", 400, 16, white, opacity=.85)

    label = "Visit mujahidk.com"
    bw = text_width(label, "sans", 700, 16) + 24 * 2 + 32 + 18
    bx, by = W - pad - bw, y - 50
    s.rect(bx, by, bw, 56, white)
    s.text(bx + 24, by + 34, label, "sans", 700, 16, ACCENT)
    s.arrow(bx + bw - 24 - 18, by + 19, ACCENT)

    h = y + 64
    s.parts.insert(0, f'<rect width="{W}" height="{h:.0f}" fill="{ACCENT}"/>')
    return s.render(h, f"{' '.join(c['name'])}. {c['intro']}")


def mission(t) -> str:
    s, y = Svg(), 64
    s.text(0, y + 14, "Mission", "sans", 500, 12, t["muted"], ls=.07, upper=True)
    for ln in wrap(CONTENT["mission"], "sans", 600, 32, 600, -.035):
        s.text(200, y + 30, ln, "sans", 600, 32, t["ink"], ls=-.035)
        y += 38
    return s.render(y + 56, "Mission: " + CONTENT["mission"])


def stack(t) -> str:
    s, x, y, gap = Svg(), 0, 20 + 15, 28
    for item in CONTENT["stack"]:
        w = text_width(item, "sans", 500, 14)
        if x and x + w > W:
            x, y = 0, y + 22
        s.text(x, y, item, "sans", 500, 14, t["muted"])
        x += w + gap
    h = y + 20 + 6
    s.line(0, 0, W, t["line"])
    s.line(0, h - 1, W, t["line"])
    return s.render(h, "Technology stack: " + ", ".join(CONTENT["stack"]))


def section_title(t, word: str, em: str) -> str:
    s, size = Svg(), 76
    y = 88 + size * .8
    s.text(-2, y, word, "sans", 850, size, t["ink"], ls=-.055)
    y += size * .95
    s.text(0, y, em, "serif", 450, size, t["ink"], ls=-.055)
    y += 48
    s.line(0, y, W, t["ink"])
    return s.render(y + 1, f"{word} {em}")


def list_row(t, num: int, title: str, body: str, tags: str | None) -> str:
    s = Svg()
    c1, gap = 56, 24
    flex = W - c1 - 18 - gap * 3
    c2 = flex / 2.4
    x2, x3 = c1 + gap, c1 + gap + c2 + gap
    c3 = flex - c2
    top = 30
    s.text(0, top + 8 + 10, f"{num:02d}", "sans", 400, 12, t["muted"])
    ty = top
    for ln in wrap(title, "sans", 820, 28, c2, -.04):
        ty += 30
        s.text(x2, ty, ln, "sans", 820, 28, t["ink"], ls=-.04)
    by = top - 2
    for ln in wrap(body, "sans", 400, 16, c3):
        by += 25
        s.text(x3, by, ln, "sans", 400, 16, t["muted"])
    if tags:
        by += 12 + 18
        s.text(x3, by, tags, "sans", 500, 13, t["ink"])
    s.arrow(W - 18, top + 6, t["ink"])
    h = max(ty + 8, by + 7) + 30
    s.line(0, h - 1, W, t["line"])
    return s.render(h, f"{num:02d} {title}: {body}")


def closing(t) -> str:
    s, size, pad = Svg(), 92, 44
    y = 84 + size * .78
    word = "Get in "
    s.text(pad, y, word, "sans", 900, size, t["band_ink"], ls=-.065)
    s.text(pad + text_width(word, "sans", 900, size, -.065), y, "touch.", "serif", 700, size,
           t["band_ink"], ls=-.05)
    label = "Contact"
    bw = text_width(label, "sans", 700, 16) + 24 * 2 + 32 + 18
    bx, by = W - pad - bw, y - 46
    s.rect(bx, by, bw, 56, t["btn"])
    s.text(bx + 24, by + 34, label, "sans", 700, 16, t["btn_ink"])
    s.arrow(bx + bw - 24 - 18, by + 19, t["btn_ink"])
    h = y + 84
    s.parts.insert(0, f'<rect width="{W}" height="{h:.0f}" fill="{t["band"]}"/>')
    return s.render(h, "Get in touch.")


def sign_off(t) -> str:
    s = Svg()
    s.text(0, 64, CONTENT["sign_line"], "sans", 500, 13, t["muted"], ls=.07, upper=True)
    size = round(W * .2233)
    y = 64 + 8 + size * .86
    name = CONTENT["name"][0]
    s.text(size * .035, y, name, "serif", 400, size, t["ink"], ls=-.045)
    s.text(size * .035 + text_width(name, "serif", 400, size, -.045), y, ".", "serif", 400, size,
           t["accent"])
    return s.render(y + size * .2 + 24, f"{CONTENT['sign_line']} {name}.")


# ─── README ──────────────────────────────────────────────────────────────────

def picture(name: str, alt: str, href: str | None = None) -> str:
    img = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
           f'<img src="assets/{name}-light.svg" width="100%" alt="{escape(alt)}"></picture>')
    return f'<a href="{href}">{img}</a>' if href else img


def readme() -> str:
    c = CONTENT
    rows = lambda items, prefix: "\n".join(
        picture(f"{prefix}-{key}", f"{title}: {body}", SITE + path)
        for key, path, title, body, _ in items)
    return f"""<!-- Generated by scripts/build.py. Edit CONTENT there, not this file. -->
<a href="{SITE}"><img src="assets/hero.svg" width="100%" alt="{escape(' '.join(c['name']))}. {escape(c['intro'])}"></a>

{picture("mission", "Mission: " + c["mission"])}
{picture("stack", "Technology stack: " + ", ".join(c["stack"]))}

{picture("title-focus", "Focus areas.")}
{rows(c["focus"], "focus")}

{picture("title-cases", "Case studies.", SITE + "/case-studies/")}
{rows(c["cases"], "case")}

<br>

{picture("closing", "Get in touch.", SITE + "/contact/")}

{picture("sign-off", c["sign_line"] + " Mujahid.")}

<p>
  <a href="mailto:mail@mujahidk.com">mail@mujahidk.com</a> &nbsp;&middot;&nbsp;
  <a href="{SITE}">mujahidk.com</a> &nbsp;&middot;&nbsp;
  <a href="https://www.linkedin.com/in/mujahidkhaleel">LinkedIn</a> &nbsp;&middot;&nbsp;
  <a href="https://x.com/mujahidkhaleel">X</a> &nbsp;&middot;&nbsp;
  <a href="{SITE}/feed.xml">RSS</a>
</p>

<sub>Opinions expressed are solely my own and do not express the views or opinions of my employer.</sub>
"""


def main():
    OUT.mkdir(exist_ok=True)
    print("Building panels:")
    save("hero", hero())
    for name, t in THEMES.items():
        save(f"mission-{name}", mission(t))
        save(f"stack-{name}", stack(t))
        save(f"title-focus-{name}", section_title(t, "Focus", "areas."))
        save(f"title-cases-{name}", section_title(t, "Case", "studies."))
        for prefix, items in (("focus", CONTENT["focus"]), ("case", CONTENT["cases"])):
            for i, (key, _, title, body, tags) in enumerate(items, 1):
                save(f"{prefix}-{key}-{name}", list_row(t, i, title, body, tags))
        save(f"closing-{name}", closing(t))
        save(f"sign-off-{name}", sign_off(t))
    (ROOT / "README.md").write_text(readme())
    print("README.md written")


if __name__ == "__main__":
    main()
