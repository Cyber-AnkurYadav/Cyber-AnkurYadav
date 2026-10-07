#!/usr/bin/env python3
"""Profile dashboard builder. Reads config.json, fetches live GitHub data, writes SVGs to assets/gen/.
No dependencies (stdlib only). Run: python scripts/build.py"""
import base64, datetime as dt, hashlib, json, math, os, re, textwrap, urllib.request
from xml.sax.saxutils import escape as esc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
OUT = os.path.join(ROOT, 'assets', 'gen'); os.makedirs(OUT, exist_ok=True)
T = CFG['theme']; USER = CFG['username']
SANS = "'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ───────────────────────── data ─────────────────────────
def get(url):
    h = {'User-Agent': 'profile-builder'}
    tok = os.environ.get('GITHUB_TOKEN')
    if tok and 'api.github.com' in url: h['Authorization'] = 'Bearer ' + tok
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25).read().decode()

def fetch():
    d = dict(ok=False, repos=0, followers=0, stars=0, prs=0, issues=0, created='', gid='', total=0, days=[], langs={})
    try:
        u = json.loads(get(f'https://api.github.com/users/{USER}'))
        d.update(ok=True, repos=u['public_repos'], followers=u['followers'], created=u['created_at'][:10], gid=u['id'])
        for r in json.loads(get(f'https://api.github.com/users/{USER}/repos?per_page=100&type=owner')):
            if r['fork']: continue
            d['stars'] += r['stargazers_count']
            try:
                for k, v in json.loads(get(r['languages_url'])).items(): d['langs'][k] = d['langs'].get(k, 0) + v
            except Exception: pass
        for k, q in (('prs', 'type:pr'), ('issues', 'type:issue')):
            try: d[k] = json.loads(get(f'https://api.github.com/search/issues?q=author:{USER}+{q}'))['total_count']
            except Exception: pass
    except Exception as e: print('api warning:', e)
    try:
        h = get(f'https://github.com/users/{USER}/contributions')
        tips = {m[0]: (0 if m[1] == 'No' else int(m[1])) for m in re.findall(r'for="(contribution-day-component-\d+-\d+)"[^>]*>(No|\d+) contributions?', h)}
        for m in re.finditer(r'data-date="([\d-]+)"[^>]*?id="(contribution-day-component-\d+-\d+)"[^>]*?data-level="(\d)"', h):
            n = tips.get(m[2], 1 if m[3] != '0' else 0)
            d['days'].append(dict(date=m[1], n=n, lv=int(m[3])))
        d['days'].sort(key=lambda x: x['date'])
        t = re.search(r'([\d,]+)\s+contributions\s+in\s+the\s+last\s+year', h)
        d['total'] = int(t[1].replace(',', '')) if t else sum(x['n'] for x in d['days'])
    except Exception as e: print('contrib warning:', e)
    return d

def streaks(days):
    best = run = 0
    for x in days:
        run = run + 1 if x['n'] > 0 else 0; best = max(best, run)
    i = len(days) - 1
    if i >= 0 and days[i]['n'] == 0: i -= 1
    cur = 0
    while i >= 0 and days[i]['n'] > 0: cur += 1; i -= 1
    return cur, best

D = fetch()
CUR, BEST = streaks(D['days'])
XP = D['total'] * 10 + D['repos'] * 50 + D['stars'] * 25 + D['prs'] * 30 + D['issues'] * 10
LVL = int(math.sqrt(XP / 100)) + 1
LO, HI = (LVL - 1) ** 2 * 100, LVL ** 2 * 100
LPCT = (XP - LO) / (HI - LO) * 100
RANKS = ['Initiate', 'Recon Rookie', 'Packet Sniffer', 'Junior Analyst', 'Pentester', 'Threat Hunter', 'Operator', 'Architect']
RANK = RANKS[min(LVL - 1, len(RANKS) - 1)]
P = CFG['progress']
DAY = max(0, min(P['days'], (dt.date.today() - dt.date.fromisoformat(P['start'])).days + 1))
PPCT = DAY / P['days'] * 100

# ───────────────────────── helpers ─────────────────────────
def svg(w, h, body, css='', defs=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{T["c1"]}"/><stop offset=".55" stop-color="{T["c2"]}"/><stop offset="1" stop-color="{T["c3"]}"/></linearGradient>'
            f'<filter id="glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>{defs}</defs>'
            f'<style>text{{font-family:{SANS}}}.m{{font-family:{MONO}}}.fb{{transform-box:fill-box;transform-origin:center}}{css}</style>{body}</svg>')

def save(name, s):
    open(os.path.join(OUT, name), 'w', encoding='utf-8').write(s)

def panel(x, y, w, h, r=20, stroke=None, op=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{T["s1"]}" stroke="{stroke or T["line"]}" stroke-opacity="{op}"/>'

def chip(x, y, text, col, w=None):
    w = w or 16 + len(text) * 7.4
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="24" rx="12" fill="{col}" fill-opacity=".13" stroke="{col}" stroke-opacity=".6"/>'
            f'<text class="m" x="{x + w / 2:.0f}" y="{y + 16}" text-anchor="middle" font-size="11" font-weight="700" fill="{col}">{esc(text)}</text>'), w

def cycle_css(name, n, secs):
    s = 100 / n
    return (f'.{name}{{opacity:0;animation:{name} {n * secs}s infinite}}'
            f'@keyframes {name}{{0%{{opacity:0}}{s * .1:.1f}%,{s * .88:.1f}%{{opacity:1}}{s:.1f}%,100%{{opacity:0}}}}')

def hexpath(cx, cy, r):
    return 'M' + ' L'.join(f'{cx + r * math.cos(math.radians(30 + 60 * k)):.1f} {cy + r * math.sin(math.radians(30 + 60 * k)):.1f}' for k in range(6)) + ' Z'

ICONS = {
    'shield': 'M12 2 L20 5 V11 C20 16 16.5 20 12 22 C7.5 20 4 16 4 11 V5 Z',
    'star': 'M12 2 L14.8 8.6 L22 9.3 L16.5 14 L18.2 21 L12 17.3 L5.8 21 L7.5 14 L2 9.3 L9.2 8.6 Z',
    'cloud': 'M7 18 a4.5 4.5 0 0 1 -.6 -8.96 A6 6 0 0 1 18 9.5 a4 4 0 0 1 0 8.5 Z',
    'flame': 'M12 2 C13 7 18 9 18 14 A6 6 0 0 1 6 14 C6 11 8 10 9 8 C10 10 11 10 12 2 Z',
    'book': 'M4 4 H11 A2 2 0 0 1 12 5 V20 A2 2 0 0 0 11 19 H4 Z M20 4 H13 A2 2 0 0 0 12 5 V20 A2 2 0 0 1 13 19 H20 Z',
    'medal': 'M12 2 a6.5 6.5 0 1 1 -.01 0 Z M8.5 13.5 L7 22 L12 19.2 L17 22 L15.5 13.5',
    'lock': 'M6 10 V8 a6 6 0 0 1 12 0 V10 H19 V21 H5 V10 Z'}

def icon(name, cx, cy, s, fill, op=1):
    return f'<path d="{ICONS[name]}" transform="translate({cx - 12 * s:.1f} {cy - 12 * s:.1f}) scale({s})" fill="{fill}" fill-opacity="{op}"/>'

def bg_grid(w, h, r=28):
    return (f'<rect width="{w}" height="{h}" rx="{r}" fill="{T["bg"]}"/><rect width="{w}" height="{h}" rx="{r}" fill="url(#gr)"/>')
GRID = '<pattern id="gr" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern>'

# ───────────────────────── progress bar ─────────────────────────
def progress_bar(x, y, w, h, pct):
    cols = P['colors']; style = P.get('style', 'gradient')
    stops = ''.join(f'<stop offset="{i / max(1, len(cols) - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(cols))
    defs = (f'<linearGradient id="pg" gradientUnits="userSpaceOnUse" x1="{x}" x2="{x + w}">{stops}</linearGradient>'
            f'<pattern id="st" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="18" fill="#fff" fill-opacity=".2"/>'
            f'<animate attributeName="x" from="0" to="18" dur="1.1s" repeatCount="indefinite"/></pattern>'
            f'<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    fw = max(h, w * pct / 100); r = h / 2
    b = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{T["s2"]}" stroke="{T["line"]}"/>'
    if style == 'segmented':
        n = 40; sw = (w - (n - 1) * 3) / n; fill = max(1, round(n * pct / 100))
        for i in range(n):
            on = i < fill
            anim = '<animate attributeName="opacity" values="1;.35;1" dur="1.4s" repeatCount="indefinite"/>' if i == fill - 1 else ''
            b += f'<rect x="{x + i * (sw + 3):.1f}" y="{y}" width="{sw:.1f}" height="{h}" rx="3" fill="{"url(#pg)" if on else T["s2"]}">{anim}</rect>'
    else:
        b += f'<clipPath id="pc"><rect x="{x}" y="{y}" width="{fw:.1f}" height="{h}" rx="{r}"/></clipPath>'
        b += f'<rect x="{x}" y="{y}" width="{fw:.1f}" height="{h}" rx="{r}" fill="url(#pg)" filter="url(#glow)" opacity=".55"/>'
        b += f'<rect x="{x}" y="{y}" width="{fw:.1f}" height="{h}" rx="{r}" fill="url(#pg)"/>'
        if style == 'stripes': b += f'<rect x="{x}" y="{y}" width="{fw:.1f}" height="{h}" rx="{r}" fill="url(#st)"/>'
        b += (f'<g clip-path="url(#pc)"><rect x="{x - 80}" y="{y}" width="70" height="{h}" fill="url(#sh)"><animate attributeName="x" from="{x - 80}" to="{x + fw:.0f}" dur="2.8s" repeatCount="indefinite"/></rect></g>')
        b += f'<circle cx="{x + fw - r:.1f}" cy="{y + r}" r="{r * .55:.1f}" fill="#fff"><animate attributeName="r" values="{r * .4:.1f};{r * .8:.1f};{r * .4:.1f}" dur="1.6s" repeatCount="indefinite"/></circle>'
    for q in (25, 50, 75): b += f'<rect x="{x + w * q / 100:.1f}" y="{y + h + 3}" width="1.5" height="4" fill="{T["muted"]}" opacity=".6"/>'
    return defs, b

# ───────────────────────── mascot ─────────────────────────
def mascot():
    c1, c2, c3 = T['c1'], T['c2'], T['c3']
    skin = '#e8b88f'
    return f'''
<ellipse cx="0" cy="124" rx="96" ry="13" fill="{c2}" opacity=".28"/>
<g class="fl">
 <path d="M-64 -20 C-82 -72 -40 -114 0 -110 C40 -114 82 -72 64 -20 C72 10 60 32 50 36 L-50 36 C-60 32 -72 10 -64 -20Z" fill="#14101f"/>
 <rect x="-12" y="26" width="24" height="22" rx="9" fill="#d9a073"/>
 <path d="M-70 124 C-72 64 -48 42 0 42 C48 42 72 64 70 124 Z" fill="#4c35b8"/>
 <path d="M-40 46 C-20 68 20 68 40 46 C28 38 -28 38 -40 46Z" fill="#3a2796"/>
 <path d="M-14 62 v24 M14 62 v24" stroke="#e5e7ff" stroke-width="3" stroke-linecap="round"/>
 <circle cx="-56" cy="-22" r="9" fill="{skin}"/><circle cx="56" cy="-22" r="9" fill="{skin}"/>
 <ellipse cx="0" cy="-24" rx="56" ry="52" fill="{skin}"/>
 <path d="M-58 -30 C-64 -86 -20 -100 4 -93 C40 -100 68 -78 58 -30 C52 -52 42 -62 26 -66 C32 -52 20 -46 8 -66 C2 -50 -10 -50 -16 -66 C-32 -58 -50 -52 -58 -30Z" fill="#1c1630"/>
 <path d="M-34 -82 C-20 -92 0 -94 16 -90" stroke="#6d5bd0" stroke-width="3" fill="none" opacity=".75" stroke-linecap="round"/>
 <g class="fb bl"><ellipse cx="-22" cy="-22" rx="12" ry="14" fill="#fff"/><ellipse cx="-22" cy="-20" rx="8.5" ry="11.5" fill="url(#ir)"/><ellipse cx="-22" cy="-20" rx="4" ry="6.5" fill="#0b1020"/><circle cx="-26" cy="-25" r="3" fill="#fff"/><circle cx="-19" cy="-14" r="1.5" fill="#fff"/></g>
 <g class="fb bl"><ellipse cx="22" cy="-22" rx="12" ry="14" fill="#fff"/><ellipse cx="22" cy="-20" rx="8.5" ry="11.5" fill="url(#ir)"/><ellipse cx="22" cy="-20" rx="4" ry="6.5" fill="#0b1020"/><circle cx="18" cy="-25" r="3" fill="#fff"/><circle cx="25" cy="-14" r="1.5" fill="#fff"/></g>
 <path d="M-35 -44 q12 -9 25 -2 M35 -44 q-12 -9 -25 -2" stroke="#14101f" stroke-width="3.5" fill="none" stroke-linecap="round"/>
 <ellipse cx="-36" cy="-2" rx="9" ry="5" fill="{c3}" opacity=".32"/><ellipse cx="36" cy="-2" rx="9" ry="5" fill="{c3}" opacity=".32"/>
 <path d="M-8 8 q8 9 16 0" stroke="#7a3b2e" stroke-width="3" fill="none" stroke-linecap="round"/>
 <path d="M-9 16 q9 12 18 0 q-9 4 -18 0Z" fill="#14101f" opacity=".9"/>
 <path d="M-62 -28 C-66 -114 66 -114 62 -28" fill="none" stroke="#11182b" stroke-width="8" stroke-linecap="round"/>
 <rect x="-74" y="-44" width="19" height="42" rx="9" fill="#11182b" stroke="{c1}" stroke-width="2.5"/><rect x="55" y="-44" width="19" height="42" rx="9" fill="#11182b" stroke="{c1}" stroke-width="2.5"/>
 <rect x="-68" y="-34" width="7" height="22" rx="3.5" fill="{c1}" class="pulse"/><rect x="61" y="-34" width="7" height="22" rx="3.5" fill="{c1}" class="pulse"/>
 <path d="M-62 84 Q-76 62 -48 56 M62 84 Q76 62 48 56" stroke="#4c35b8" stroke-width="15" fill="none" stroke-linecap="round"/>
 <rect x="-62" y="60" width="124" height="58" rx="9" fill="#151a30" stroke="url(#g)" stroke-width="2"/>
 <path d="M0 71 l15 6 v13 c0 11 -7 18 -15 22 c-8 -4 -15 -11 -15 -22 v-13 Z" fill="none" stroke="{c1}" stroke-width="2.5" class="pulse"/>
 <path d="M-6 91 l5 5 l9 -11" stroke="{c1}" stroke-width="2.5" fill="none" stroke-linecap="round" class="pulse"/>
 <rect x="-76" y="118" width="152" height="8" rx="4" fill="#0e1226" stroke="{T['line']}"/>
 <circle class="ty1" cx="-46" cy="56" r="9.5" fill="{skin}"/><circle class="ty2" cx="46" cy="56" r="9.5" fill="{skin}"/>
</g>'''

MASCOT_CSS = ('.fl{animation:fl 4s ease-in-out infinite}@keyframes fl{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}'
              '.bl{animation:bl 4.5s infinite}@keyframes bl{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.07)}}'
              '.ty1{animation:ty .45s ease-in-out infinite alternate}.ty2{animation:ty .45s ease-in-out .22s infinite alternate}@keyframes ty{to{transform:translateY(-4px)}}'
              '.pulse{animation:pu 2s ease-in-out infinite}@keyframes pu{0%,100%{opacity:1}50%{opacity:.45}}'
              '.fw1{animation:fw 5s ease-in-out infinite}.fw2{animation:fw 6.5s ease-in-out 1s infinite}@keyframes fw{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}'
              '.tw{animation:tw 2.4s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}'
              '.cur{animation:cu 1s steps(1) infinite}@keyframes cu{50%{opacity:0}}')

# ───────────────────────── hero ─────────────────────────
def hero():
    W, H = 880, 420; c1, c2, c3 = T['c1'], T['c2'], T['c3']
    pdefs, pbar = progress_bar(28, 42, 824, 12, PPCT)
    roles = CFG['roles']; msgs = CFG['mascot_messages']
    css = MASCOT_CSS + cycle_css('rl', len(roles), 3) + cycle_css('bm', len(msgs), 3)
    body = bg_grid(W, H) + f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="27" fill="none" stroke="url(#g)" stroke-opacity=".5" stroke-width="2"/>'
    body += (f'<circle cx="150" cy="330" r="150" fill="{c2}" opacity=".13" filter="url(#bl)"><animate attributeName="cx" values="150;230;150" dur="9s" repeatCount="indefinite"/></circle>'
             f'<circle cx="730" cy="120" r="140" fill="{c1}" opacity=".10" filter="url(#bl)"><animate attributeName="cy" values="120;200;120" dur="8s" repeatCount="indefinite"/></circle>')
    body += (f'<text class="m" x="28" y="32" font-size="11.5" font-weight="700" fill="{c1}" letter-spacing="1.5">{esc(P["label"])}</text>'
             f'<text class="m" x="852" y="32" font-size="11.5" font-weight="700" fill="{T["muted"]}" text-anchor="end">DAY {DAY} / {P["days"]}  ·  {PPCT:.0f}%</text>') + pbar
    body += f'<text class="m" x="28" y="106" font-size="13" fill="{T["muted"]}">ankur@kali:~$ whoami<tspan class="cur" fill="{c1}"> ▌</tspan></text>'
    body += f'<text x="28" y="170" font-size="60" font-weight="900" fill="url(#g)" letter-spacing="1">{esc(CFG["name"])}</text>'
    for i, r in enumerate(roles):
        body += f'<g class="rl" style="animation-delay:{i * 3}s"><text class="m" x="30" y="212" font-size="19" font-weight="700" fill="{c1}">&gt; <tspan fill="#fff">{esc(r)}</tspan></text></g>'
    body += f'<text x="30" y="246" font-size="14.5" fill="{T["muted"]}">{esc(CFG["tagline"])}</text>'
    x = 30
    for t, col in CFG['chips']:
        s, w = chip(x, 266, t, col); body += s; x += w + 10
    body += (f'<rect x="28" y="318" width="500" height="40" rx="12" fill="{T["s1"]}" stroke="{T["line"]}"/>'
             f'<text class="m" x="44" y="343" font-size="13" font-weight="700" fill="#fff">{esc(CFG["mission"])}</text>'
             f'<text class="m" x="28" y="386" font-size="10.5" font-weight="700" fill="{c3}" letter-spacing="1.5">NOW BUILDING</text>'
             f'<text x="28" y="404" font-size="13" fill="#d7dcf5">{esc(CFG["building"])}</text>')
    # mascot panel
    body += (f'<clipPath id="pn"><rect x="560" y="78" width="292" height="326" rx="24"/></clipPath>'
             f'<rect x="560" y="78" width="292" height="326" rx="24" fill="{T["s1"]}" stroke="url(#g)" stroke-opacity=".6" stroke-width="1.5"/>'
             f'<g clip-path="url(#pn)"><circle cx="706" cy="260" r="120" fill="url(#rg)"/>'
             f'<rect x="560" y="80" width="292" height="2" fill="{c1}" opacity=".55"><animate attributeName="y" values="80;402;80" dur="6s" repeatCount="indefinite"/></rect></g>')
    body += (f'<g class="fw1"><rect x="572" y="186" width="82" height="50" rx="8" fill="{T["bg"]}" stroke="{c1}" stroke-opacity=".7"/><rect x="572" y="186" width="82" height="11" rx="5" fill="{c1}" opacity=".25"/>'
             f'<text class="m" x="580" y="215" font-size="8.5" fill="{c1}">$ nmap -sV</text><text class="m" x="580" y="227" font-size="8.5" fill="{T["muted"]}">22/tcp open</text></g>'
             f'<g class="fw2"><rect x="766" y="150" width="78" height="50" rx="8" fill="{T["bg"]}" stroke="{c3}" stroke-opacity=".7"/><rect x="766" y="150" width="78" height="11" rx="5" fill="{c3}" opacity=".25"/>'
             f'<text class="m" x="774" y="179" font-size="8.5" fill="{c3}">root@kali</text><text class="m" x="774" y="191" font-size="8.5" fill="{T["muted"]}">flag{{...}}</text></g>')
    for sx, sy, dl in ((590, 130, 0), (830, 250, .8), (600, 360, 1.5), (820, 372, .4)):
        body += f'<path class="tw" style="animation-delay:{dl}s" d="M{sx} {sy - 6} L{sx + 1.8} {sy - 1.8} L{sx + 6} {sy} L{sx + 1.8} {sy + 1.8} L{sx} {sy + 6} L{sx - 1.8} {sy + 1.8} L{sx - 6} {sy} L{sx - 1.8} {sy - 1.8}Z" fill="#fff"/>'
    body += f'<g transform="translate(706 262)">{mascot()}</g>'
    body += (f'<path d="M690 130 l10 12 l12 -12 Z" fill="{T["s2"]}" stroke="{c1}" stroke-opacity=".6"/><rect x="580" y="96" width="196" height="34" rx="17" fill="{T["s2"]}" stroke="{c1}" stroke-opacity=".6"/><rect x="691" y="129" width="20" height="3" fill="{T["s2"]}"/>')
    for i, m in enumerate(msgs):
        body += f'<g class="bm" style="animation-delay:{i * 3}s"><text class="m" x="678" y="118" font-size="12" font-weight="700" fill="#fff" text-anchor="middle">{esc(m)}</text></g>'
    defs = (GRID + pdefs + '<filter id="bl" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="40"/></filter>'
            f'<radialGradient id="rg"><stop offset="0" stop-color="{c2}" stop-opacity=".45"/><stop offset="1" stop-color="{c2}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="ir" cx=".5" cy=".4"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></radialGradient>')
    save('hero.svg', svg(W, H, body, css, defs))

# ───────────────────────── ID card ─────────────────────────
def idcard():
    W, H = 880, 330; c1, c2, c3 = T['c1'], T['c2'], T['c3']
    av = base64.b64encode(open(os.path.join(ROOT, 'assets', 'avatar.jpg'), 'rb').read()).decode()
    b = bg_grid(W, H, 26) + f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="25" fill="none" stroke="url(#g)" stroke-width="2.5"/>'
    b += f'<clipPath id="cc"><rect width="{W}" height="{H}" rx="26"/></clipPath><g clip-path="url(#cc)"><rect x="-200" y="0" width="140" height="{H}" fill="url(#sw)" transform="skewX(-18)"><animate attributeName="x" from="-300" to="1100" dur="7s" repeatCount="indefinite"/></rect></g>'
    b += f'<rect x="0" y="0" width="{W}" height="34" fill="{T["s2"]}" clip-path="url(#cc)"/><circle cx="26" cy="17" r="4" fill="{c3}"/><circle cx="42" cy="17" r="4" fill="{T["gold"]}"/><circle cx="58" cy="17" r="4" fill="{c1}"/>'
    b += f'<text class="m" x="{W / 2}" y="21" font-size="10.5" fill="{T["muted"]}" text-anchor="middle" letter-spacing="2">OPERATOR ID  //  ACCESS: AUTHORIZED</text>'
    # avatar
    b += (f'<circle class="fb spin" cx="130" cy="150" r="92" fill="none" stroke="url(#g)" stroke-width="2.5" stroke-dasharray="6 9"/>'
          f'<clipPath id="av"><circle cx="130" cy="150" r="78"/></clipPath><circle cx="130" cy="150" r="80" fill="{T["s2"]}"/>'
          f'<image href="data:image/jpeg;base64,{av}" x="52" y="72" width="156" height="156" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>'
          f'<circle cx="130" cy="150" r="78" fill="none" stroke="{T["bg"]}" stroke-width="3"/>')
    pill = f'LVL {LVL:02d}  ·  {RANK.upper()}'; pw = 30 + len(pill) * 7.2
    b += (f'<rect x="{130 - pw / 2:.0f}" y="262" width="{pw:.0f}" height="28" rx="14" fill="{T["bg"]}" stroke="url(#g)" stroke-width="1.8"/>'
          f'<text class="m" x="130" y="281" font-size="11.5" font-weight="800" fill="#fff" text-anchor="middle">{pill}</text>')
    # info
    b += (f'<text x="262" y="92" font-size="40" font-weight="900" fill="#fff" letter-spacing=".5">{esc(CFG["name"])}</text>'
          f'<text class="m" x="264" y="120" font-size="15" font-weight="700" fill="url(#g)" letter-spacing="1.5">{esc(CFG["role"].upper())}</text>'
          f'<rect x="262" y="136" width="440" height="1.5" fill="{T["line"]}"/>')
    fields = [('GITHUB', '@' + USER), ('CLASS', 'Red + Blue Team'), ('STATUS', 'ACTIVE LEARNER'),
              ('JOINED', D['created'] or '—'), ('FOCUS', 'DFIR · OSINT'), ('REPOS / FOLLOWERS', f'{D["repos"]}  /  {D["followers"]}' if D['ok'] else '—')]
    for i, (k, v) in enumerate(fields):
        x = (262, 436, 596)[i % 3]; y = 164 + (i // 3) * 52
        b += f'<text class="m" x="{x}" y="{y}" font-size="9.5" fill="{T["muted"]}" letter-spacing="1.5">{k}</text><text x="{x}" y="{y + 20}" font-size="13" font-weight="700" fill="#e9ecff">{esc(v)}</text>'
    b += (f'<text class="m" x="262" y="278" font-size="10" fill="{c1}" letter-spacing="1.5" font-weight="700">XP  {XP:,} / {HI:,}</text>'
          f'<text class="m" x="702" y="278" font-size="10" fill="{T["muted"]}" text-anchor="end">{LPCT:.0f}% TO LVL {LVL + 1:02d}</text>'
          f'<rect x="262" y="286" width="440" height="10" rx="5" fill="{T["s2"]}" stroke="{T["line"]}"/>'
          f'<rect class="fb xp" x="262" y="286" width="{max(10, 440 * LPCT / 100):.0f}" height="10" rx="5" fill="url(#pg)"/>')
    # barcode + pseudo-QR
    hsh = hashlib.sha256(USER.encode()).digest()
    x = 742
    for i in range(44):
        w = 1 + (hsh[i % 32] >> (i % 5)) % 3; b += f'<rect x="{x}" y="52" width="{w}" height="46" fill="#cfd6ff" opacity=".85"/>'; x += w + 1.4
        if x > 856: break
    b += f'<text class="m" x="742" y="112" font-size="9" fill="{T["muted"]}" letter-spacing="1.2">ID-{D["gid"] or hsh.hex()[:8].upper()}</text>'
    qx, qy, cs = 752, 134, 8
    for fr, fc in ((0, 0), (0, 8), (8, 0)):
        b += f'<rect x="{qx + fc * cs + 1.5}" y="{qy + fr * cs + 1.5}" width="{3 * cs - 3}" height="{3 * cs - 3}" rx="3" fill="none" stroke="{c1}" stroke-width="3"/><rect x="{qx + fc * cs + 8}" y="{qy + fr * cs + 8}" width="{cs}" height="{cs}" rx="2" fill="{c1}"/>'
    for r in range(11):
        for c in range(11):
            if (r < 4 and c < 4) or (r < 4 and c > 6) or (r > 6 and c < 4): continue
            if (hsh[(r * 11 + c) % 32] >> (c % 7)) & 1: b += f'<rect x="{qx + c * cs}" y="{qy + r * cs}" width="{cs - 1.5}" height="{cs - 1.5}" rx="2" fill="#cfd6ff" opacity=".8"/>'
    b += f'<text class="m" x="742" y="262" font-size="9" fill="{T["muted"]}" letter-spacing="1.2">SCAN // PROFILE</text><rect x="742" y="272" width="112" height="24" rx="12" fill="none" stroke="{c3}"/><text class="m" x="798" y="288" font-size="10" font-weight="800" fill="{c3}" text-anchor="middle">VERIFIED ✓</text>'
    css = ('.spin{animation:sp 24s linear infinite}@keyframes sp{to{transform:rotate(360deg)}}'
           '.xp{transform-origin:left center;animation:xg 2.2s ease-out}@keyframes xg{from{transform:scaleX(0)}}'
           '.pulse{animation:pu 2s infinite}@keyframes pu{50%{opacity:.4}}')
    pd, _ = progress_bar(262, 286, 440, 10, LPCT)
    defs = GRID + pd + '<linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    save('idcard.svg', svg(W, H, b, css, defs))

# ───────────────────────── streak ─────────────────────────
def streak():
    W, H = 880, 250; c1, c2, c3 = T['c1'], T['c2'], T['c3']
    b = panel(0, 0, 268, H) + panel(284, 0, 232, H) + panel(532, 0, 348, H)
    # current
    b += (f'<g transform="translate(62 96)"><g class="fb fire"><path d="M0 -40 C12 -20 28 -10 28 10 C28 28 14 40 0 40 C-14 40 -28 28 -28 10 C-28 -4 -18 -12 -14 -26 C-9 -16 -4 -14 0 -40Z" fill="{c3}" filter="url(#glow)"/>'
          f'<path d="M0 -8 C6 2 14 8 14 20 C14 30 7 36 0 36 C-7 36 -14 30 -14 20 C-14 12 -8 8 0 -8Z" fill="{T["gold"]}"/></g></g>'
          f'<text x="112" y="116" font-size="66" font-weight="900" fill="url(#g)">{CUR}</text>'
          f'<text class="m" x="24" y="30" font-size="10.5" font-weight="700" fill="{T["muted"]}" letter-spacing="2">CURRENT STREAK</text>'
          f'<text class="m" x="112" y="140" font-size="12" font-weight="700" fill="#fff">{"DAY" if CUR == 1 else "DAYS"} IN A ROW</text>')
    ms = next((m for m in (3, 7, 14, 30, 60, 100, 200, 365) if m > CUR), 365)
    b += (f'<text class="m" x="24" y="196" font-size="10" fill="{T["muted"]}" letter-spacing="1.5">NEXT MILESTONE · {ms} DAYS</text>'
          f'<rect x="24" y="206" width="220" height="10" rx="5" fill="{T["s2"]}" stroke="{T["line"]}"/><rect class="fb gr" x="24" y="206" width="{max(10, 220 * CUR / ms):.0f}" height="10" rx="5" fill="url(#g)"/>')
    # longest
    b += (f'<text class="m" x="308" y="30" font-size="10.5" font-weight="700" fill="{T["muted"]}" letter-spacing="2">LONGEST STREAK</text>'
          f'<text x="308" y="116" font-size="66" font-weight="900" fill="{T["gold"]}">{BEST}</text>'
          f'<text class="m" x="308" y="140" font-size="12" font-weight="700" fill="#fff">{"DAY" if BEST == 1 else "DAYS"} · PERSONAL BEST</text>'
          f'<text class="m" x="308" y="196" font-size="10" fill="{T["muted"]}" letter-spacing="1.5">CURRENT vs BEST</text>'
          f'<rect x="308" y="206" width="184" height="10" rx="5" fill="{T["s2"]}" stroke="{T["line"]}"/><rect class="fb gr" x="308" y="206" width="{max(10, 184 * CUR / max(1, BEST)):.0f}" height="10" rx="5" fill="{T["gold"]}"/>')
    b += icon('medal', 478, 40, 1.1, T['gold'], .9)
    # heatmap
    b += (f'<text class="m" x="556" y="30" font-size="10.5" font-weight="700" fill="{T["muted"]}" letter-spacing="2">LAST 18 WEEKS</text>'
          f'<text class="m" x="860" y="30" font-size="10.5" font-weight="700" fill="{c1}" text-anchor="end">{D["total"]:,} CONTRIBUTIONS / YR</text>')
    weeks = [D['days'][i:i + 7] for i in range(0, len(D['days']), 7)][-18:]
    for ci, wk in enumerate(weeks):
        for ri, day in enumerate(wk):
            b += f'<rect class="fb cell" style="animation-delay:{ci * .05:.2f}s" x="{556 + ci * 17}" y="{50 + ri * 17}" width="14" height="14" rx="4" fill="{T["heat"][day["lv"]]}"/>'
    b += f'<text class="m" x="556" y="226" font-size="9.5" fill="{T["muted"]}">LESS</text>'
    for i, col in enumerate(T['heat']): b += f'<rect x="{592 + i * 18}" y="216" width="13" height="13" rx="4" fill="{col}"/>'
    b += f'<text class="m" x="690" y="226" font-size="9.5" fill="{T["muted"]}">MORE</text>'
    css = ('.fire{animation:fi 1.3s ease-in-out infinite}@keyframes fi{0%,100%{transform:scale(1) rotate(-2deg)}50%{transform:scale(1.08,1.12) rotate(2deg)}}'
           '.gr{transform-origin:left center;animation:gw 1.8s ease-out}@keyframes gw{from{transform:scaleX(0)}}'
           '.cell{animation:ce .5s ease-out backwards}@keyframes ce{from{opacity:0}}')
    save('streak.svg', svg(W, H, b, css))

# ───────────────────────── stats + languages ─────────────────────────
def stats():
    W, H = 880, 340; c1, c2, c3 = T['c1'], T['c2'], T['c3']
    b = panel(0, 0, 500, H) + panel(516, 0, 364, H)
    b += f'<text class="m" x="24" y="30" font-size="10.5" font-weight="700" fill="{T["muted"]}" letter-spacing="2">PLAYER STATS</text>'
    tiles = [('CONTRIBUTIONS', D['total'], c1), ('REPOSITORIES', D['repos'], c2), ('STARS', D['stars'], T['gold']),
             ('PULL REQUESTS', D['prs'], c3), ('ISSUES', D['issues'], c1), ('FOLLOWERS', D['followers'], c2)]
    for i, (k, v, col) in enumerate(tiles):
        v = f'{v:,}' if (D['ok'] or k == 'CONTRIBUTIONS') else '—'
        x = 24 + (i % 3) * 156; y = 46 + (i // 3) * 82
        b += (f'<rect x="{x}" y="{y}" width="146" height="72" rx="14" fill="{T["s2"]}" stroke="{T["line"]}"/><rect x="{x}" y="{y + 16}" width="3.5" height="40" rx="2" fill="{col}"/>'
              f'<text x="{x + 18}" y="{y + 40}" font-size="28" font-weight="900" fill="{col}">{v}</text><text class="m" x="{x + 18}" y="{y + 58}" font-size="9" fill="{T["muted"]}" letter-spacing="1.2">{k}</text>')
    # monthly sparkline
    months = {}
    for x in D['days']: months[x['date'][:7]] = months.get(x['date'][:7], 0) + x['n']
    vals = [months[k] for k in sorted(months)][-12:] or [0]
    mx = max(max(vals), 1); n = len(vals); x0, x1, y0, y1 = 36, 476, 298, 246
    pts = [(x0 + (x1 - x0) * i / max(1, n - 1), y0 - (y0 - y1) * v / mx) for i, v in enumerate(vals)]
    line = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    b += (f'<text class="m" x="24" y="226" font-size="10" fill="{T["muted"]}" letter-spacing="1.5">MONTHLY ACTIVITY</text><text class="m" x="476" y="226" font-size="10" fill="{c1}" text-anchor="end">PEAK {mx}</text>'
          f'<path d="{line} L{x1} {y0} L{x0} {y0} Z" fill="url(#af)" opacity=".5"/><path class="dr" d="{line}" fill="none" stroke="url(#g)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>')
    for x, y in pts: b += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{T["bg"]}" stroke="{c1}" stroke-width="2"/>'
    b += f'<rect x="24" y="{y0 + 8}" width="452" height="1" fill="{T["line"]}"/><text class="m" x="24" y="324" font-size="9" fill="{T["muted"]}">12 MONTHS AGO</text><text class="m" x="476" y="324" font-size="9" fill="{T["muted"]}" text-anchor="end">NOW</text>'
    # languages
    b += f'<text class="m" x="540" y="30" font-size="10.5" font-weight="700" fill="{T["muted"]}" letter-spacing="2">TOP LANGUAGES</text>'
    tot = sum(D['langs'].values()) or 1; top = sorted(D['langs'].items(), key=lambda kv: -kv[1])[:5]
    pal = [c1, c2, c3, T['gold'], '#60a5fa']
    if top:
        x = 540
        for i, (k, v) in enumerate(top):
            w = 324 * v / tot; b += f'<rect x="{x:.1f}" y="48" width="{max(w - 2, 3):.1f}" height="14" rx="5" fill="{pal[i]}"/>'; x += w
        for i, (k, v) in enumerate(top):
            y = 98 + i * 44
            b += (f'<circle cx="548" cy="{y - 4}" r="5" fill="{pal[i]}"/><text x="564" y="{y}" font-size="14" font-weight="700" fill="#fff">{esc(k)}</text><text class="m" x="860" y="{y}" font-size="12" fill="{T["muted"]}" text-anchor="end">{100 * v / tot:.1f}%</text>'
                  f'<rect x="540" y="{y + 10}" width="320" height="6" rx="3" fill="{T["s2"]}"/><rect class="fb gr" style="animation-delay:{i * .15}s" x="540" y="{y + 10}" width="{max(6, 320 * v / tot):.0f}" height="6" rx="3" fill="{pal[i]}"/>')
    else:
        b += f'<text x="540" y="100" font-size="13" fill="{T["muted"]}">Language mix loads on the next automated build.</text>'
    css = ('.dr{stroke-dasharray:1;animation:dr 2.4s ease-out}@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}'
           '.gr{transform-origin:left center;animation:gw 1.6s ease-out backwards}@keyframes gw{from{transform:scaleX(0)}}')
    defs = f'<linearGradient id="af" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c2}" stop-opacity=".7"/><stop offset="1" stop-color="{c2}" stop-opacity="0"/></linearGradient>'
    save('stats.svg', svg(W, H, b, css, defs))

# ───────────────────────── achievements ─────────────────────────
def achievements():
    W = 880; cw, ch, gap = 205, 122, 20; items = CFG['achievements']; rows = math.ceil(len(items) / 4); H = rows * ch + (rows - 1) * gap
    b = ''
    for i, a in enumerate(items):
        x = (i % 4) * (cw + gap); y = (i // 4) * (ch + gap)
        st = a.get('state')
        if a.get('rule'): st = 'unlocked' if BEST >= int(a['rule'].replace('streak', '')) else 'locked'
        col = {'unlocked': T['c1'], 'progress': T['gold'], 'locked': T['muted']}[st]
        lab = {'unlocked': 'UNLOCKED', 'progress': 'IN PROGRESS', 'locked': 'LOCKED'}[st]
        dim = .45 if st == 'locked' else 1
        b += f'<g opacity="{dim}">' + panel(x, y, cw, ch, 18, col if st != 'locked' else T['line'], .55)
        b += f'<path d="{hexpath(x + 40, y + 46, 25)}" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-width="2"/>'
        b += icon('lock' if st == 'locked' else a['icon'], x + 40, y + 46, 1.0, col)
        for j, ln in enumerate(textwrap.wrap(a['title'], 14)[:2]):
            b += f'<text x="{x + 76}" y="{y + 40 + j * 16}" font-size="13" font-weight="800" fill="#fff">{esc(ln)}</text>'
        b += f'<text class="m" x="{x + 76}" y="{y + 76}" font-size="9" fill="{T["muted"]}">{esc(textwrap.shorten(a["sub"], 20, placeholder="…"))}</text>'
        s, _ = chip(x + 16, y + 88, lab, col, 16 + len(lab) * 7.2); b += s + '</g>'
        if st == 'unlocked':
            b += f'<g clip-path="url(#k{i})"><rect x="{x - 60}" y="{y}" width="40" height="{ch}" fill="url(#sh)" transform="skewX(-20)" opacity=".5"><animate attributeName="x" from="{x - 60}" to="{x + cw + 40}" dur="5s" begin="{i * .6}s" repeatCount="indefinite"/></rect></g>'
    defs = ''.join(f'<clipPath id="k{i}"><rect x="{(i % 4) * (cw + gap)}" y="{(i // 4) * (ch + gap)}" width="{cw}" height="{ch}" rx="18"/></clipPath>' for i in range(len(items)))
    defs += '<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    save('achievements.svg', svg(W, H, b, '', defs))

# ───────────────────────── arsenal + projects ─────────────────────────
def arsenal():
    W, H = 880, 300; b = ''
    x = 0
    # tool ticker
    b += f'<clipPath id="tk"><rect width="{W}" height="46" rx="23"/></clipPath>' + panel(0, 0, W, 46, 23) + '<g clip-path="url(#tk)"><g class="tick">'
    row = ''; xx = 20; k = 0
    for rep in range(2):
        for t in CFG['arsenal_chips']:
            s, w = chip(xx, 11, t, [T['c1'], T['c2'], T['c3']][k % 3]); row += s; xx += w + 10; k += 1
    b += row + '</g></g>'
    half = xx / 2
    for i, a in enumerate(CFG['arsenal']):
        x = i * 224; y = 62; col = a['color']
        b += panel(x, y, 208, 238, 20, col, .5) + f'<rect x="{x + 24}" y="{y}" width="160" height="4" rx="2" fill="{col}" opacity=".9"/>'
        b += f'<circle cx="{x + 26}" cy="{y + 36}" r="6" fill="{col}" filter="url(#glow)"/><text class="m" x="{x + 42}" y="{y + 41}" font-size="12.5" font-weight="800" fill="{col}" letter-spacing="2">{esc(a["title"])}</text>'
        for j, it in enumerate(a['items']):
            yy = y + 66 + j * 40
            b += f'<rect x="{x + 16}" y="{yy}" width="176" height="32" rx="10" fill="{T["s2"]}" stroke="{T["line"]}"/><rect x="{x + 16}" y="{yy + 8}" width="3" height="16" rx="1.5" fill="{col}"/><text x="{x + 32}" y="{yy + 21}" font-size="13" font-weight="600" fill="#e9ecff">{esc(it)}</text>'
    css = f'.tick{{animation:tk 26s linear infinite}}@keyframes tk{{to{{transform:translateX(-{half:.0f}px)}}}}'
    save('arsenal.svg', svg(W, H, b, css))

def projects():
    W, H = 880, 330; b = ''
    for i, p in enumerate(CFG['projects']):
        x = (i % 2) * 450; y = (i // 2) * 170; col = p['color']
        b += panel(x, y, 430, 160, 22, col, .5) 
        b += (f'<rect x="{x + 20}" y="{y + 22}" width="56" height="56" rx="16" fill="{col}" fill-opacity=".15" stroke="{col}"/><text class="m" x="{x + 48}" y="{y + 57}" font-size="{16 if len(p["code"]) < 3 else 13}" font-weight="900" fill="{col}" text-anchor="middle">{esc(p["code"])}</text>'
              f'<text x="{x + 92}" y="{y + 44}" font-size="20" font-weight="800" fill="#fff">{esc(p["title"])}</text><text class="m" x="{x + 92}" y="{y + 66}" font-size="11" fill="{col}">{esc(p["tags"])}</text>')
        for j, ln in enumerate(textwrap.wrap(p['text'], 56)[:3]):
            b += f'<text x="{x + 22}" y="{y + 102 + j * 19}" font-size="13" fill="#b9c0e0">{esc(ln)}</text>'
        s, _ = chip(x + 330, y + 14, 'BUILDING', col, 84); b += s
    save('projects.svg', svg(W, H, b, '.pulse{animation:pu 2s infinite}@keyframes pu{50%{opacity:.4}}'))

# ───────────────────────── nav / headers / footer ─────────────────────────
def nav():
    items = [('profile', 'PROFILE', T['c1']), ('arsenal', 'ARSENAL', T['c2']), ('projects', 'PROJECTS', T['c3']), ('dashboard', 'DASHBOARD', '#60a5fa'), ('achievements', 'ACHIEVEMENTS', T['gold']), ('connect', 'CONNECT', T['c1'])]
    for k, t, col in items:
        w = 44 + len(t) * 8.4
        b = (f'<rect x="1" y="1" width="{w - 2:.0f}" height="38" rx="19" fill="{T["s1"]}" stroke="{col}" stroke-opacity=".6" stroke-width="1.5"/><circle class="d" cx="20" cy="20" r="4" fill="{col}"/>'
             f'<text class="m" x="34" y="25" font-size="12" font-weight="800" fill="#fff" letter-spacing="1.2">{t}</text>')
        save(f'nav-{k}.svg', svg(round(w), 40, b, '.d{animation:pu 2s infinite}@keyframes pu{50%{opacity:.3}}'))

def headers():
    for i, (k, t, sub) in enumerate([('profile', 'PROFILE', 'who I am · what I focus on'), ('arsenal', 'SECURITY ARSENAL', 'tools · categories'), ('projects', 'WHAT I\'M BUILDING', 'experiments · labs'),
                                     ('dashboard', 'DASHBOARD', 'streak · stats · activity'), ('achievements', 'ACHIEVEMENTS', 'badges · certifications'), ('connect', 'CONNECT', 'find me online')], 1):
        b = (f'<text class="m" x="2" y="42" font-size="30" font-weight="900" fill="url(#g)">{i:02d}</text><text x="56" y="34" font-size="22" font-weight="900" fill="#fff" letter-spacing="1.5">{esc(t)}</text>'
             f'<text class="m" x="57" y="52" font-size="10.5" fill="{T["muted"]}" letter-spacing="1.5">{esc(sub)}</text>'
             f'<rect x="330" y="30" width="550" height="2" rx="1" fill="url(#g)" opacity=".5"/><circle r="5" cy="31" fill="{T["c1"]}" filter="url(#glow)"><animate attributeName="cx" values="330;875;330" dur="6s" repeatCount="indefinite"/></circle>')
        save(f'h-{k}.svg', svg(880, 64, b))

def footer():
    W = 880; txt = '   KEEP LEARNING  •  KEEP HACKING  •  KEEP GROWING  •  KEEP SECURING   '
    wd = len(txt) * 13.2
    b = f'<clipPath id="f"><rect width="{W}" height="54" rx="27"/></clipPath>' + panel(0, 0, W, 54, 27, T['c2'], .5) + '<g clip-path="url(#f)"><g class="mq">'
    for i in range(3): b += f'<text class="m" x="{i * wd:.0f}" y="34" font-size="18" font-weight="800" fill="url(#g)" xml:space="preserve">{esc(txt)}</text>'
    b += '</g></g>'
    save('footer.svg', svg(W, 54, b, f'.mq{{animation:mq 20s linear infinite}}@keyframes mq{{to{{transform:translateX(-{wd:.0f}px)}}}}'))

for fn in (hero, idcard, streak, stats, achievements, arsenal, projects, nav, headers, footer): fn()
print(f'built · day {DAY}/{P["days"]} · streak {CUR}/{BEST} · lvl {LVL} ({XP} xp) · contributions {D["total"]} · repos {D["repos"]}')
