import re, sys, html

def inline(t):
    t = html.escape(t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'(?<!href=")(?<!>)(https?://[^\s<)]+)', r'<a href="\1">\1</a>', t)
    return t

def convert(md):
    lines = md.split('\n'); out = []; i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):                                  # code fence
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith('```'):
                buf.append(html.escape(lines[i])); i += 1
            i += 1; out.append('<pre><code>' + '\n'.join(buf) + '</code></pre>'); continue
        if re.match(r'^\s*\|.*\|\s*$', ln) and i+1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i+1]):
            hdr = [c.strip() for c in ln.strip().strip('|').split('|')]
            i += 2; rows = []
            while i < len(lines) and re.match(r'^\s*\|.*\|\s*$', lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            t = '<table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in hdr) + '</tr></thead><tbody>'
            for r in rows:
                t += '<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>'
            out.append(t + '</tbody></table>'); continue
        m = re.match(r'^(#{1,6})\s+(.*)$', ln)
        if m:
            lv = len(m.group(1)); out.append(f'<h{lv}>{inline(m.group(2))}</h{lv}>'); i += 1; continue
        if re.match(r'^\s*---+\s*$', ln): out.append('<hr>'); i += 1; continue
        if re.match(r'^\s*[-*]\s+', ln) or re.match(r'^\s*\d+\.\s+', ln):
            ordered = bool(re.match(r'^\s*\d+\.\s+', ln)); items = []
            while i < len(lines) and (re.match(r'^\s*[-*]\s+', lines[i]) or re.match(r'^\s*\d+\.\s+', lines[i]) or (items and lines[i].startswith('  ') and lines[i].strip())):
                if re.match(r'^\s*[-*]\s+', lines[i]) or re.match(r'^\s*\d+\.\s+', lines[i]):
                    items.append(re.sub(r'^\s*(?:[-*]|\d+\.)\s+', '', lines[i]))
                else: items[-1] += ' ' + lines[i].strip()
                i += 1
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + f'</{tag}>'); continue
        if ln.strip() == '': i += 1; continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,6}\s|```|\s*\|)', lines[i]) and not re.match(r'^\s*[-*]\s+', lines[i]) and not re.match(r'^\s*---+\s*$', lines[i]):
            para.append(lines[i]); i += 1
        if para: out.append('<p>' + inline(' '.join(para)) + '</p>')
    return '\n'.join(out)

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Calibri, Arial, sans-serif; font-size: 9.6pt; line-height: 1.5;
       color: #14181f; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 20pt; color: #0b2447; margin: 0 0 4pt; letter-spacing: -.2pt; }
h2 { font-size: 13pt; color: #0b2447; margin: 16pt 0 6pt; padding-bottom: 3pt;
     border-bottom: 1.4pt solid #0b2447; break-after: avoid; }
h3 { font-size: 10.8pt; color: #1b3a5c; margin: 11pt 0 4pt; break-after: avoid; }
p { margin: 0 0 6pt; text-align: justify; }
ul, ol { margin: 0 0 7pt; padding-left: 16pt; }
li { margin-bottom: 3pt; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.6pt;
       background: #eef1f5; padding: .5pt 3pt; border-radius: 2pt; }
pre { background: #f6f8fa; border: .6pt solid #d3dae3; border-left: 2.5pt solid #0b2447;
      padding: 7pt 9pt; margin: 0 0 8pt; break-inside: avoid; overflow: hidden; }
pre code { background: none; padding: 0; font-size: 6.9pt; line-height: 1.28; white-space: pre; }
table { border-collapse: collapse; width: 100%; margin: 0 0 9pt; font-size: 8.7pt; break-inside: avoid; }
th { background: #0b2447; color: #fff; text-align: left; padding: 4.5pt 6pt; font-weight: 600; }
td { border: .6pt solid #ccd4de; padding: 4pt 6pt; vertical-align: top; }
tbody tr:nth-child(even) { background: #f5f7fa; }
hr { border: 0; border-top: .6pt solid #d3dae3; margin: 10pt 0; }
a { color: #12508f; text-decoration: none; }
h2, h3 { break-after: avoid; }
"""

md = open(sys.argv[1], encoding='utf-8').read()
open(sys.argv[2], 'w', encoding='utf-8').write(
    f'<!doctype html><html><head><meta charset="utf-8"><title>SUTRA HLD</title>'
    f'<style>{CSS}</style></head><body>{convert(md)}</body></html>')
print("html written:", sys.argv[2])
