#!/usr/bin/env python3
"""Stampa testatine e folii sulle pagine dei capitoli e cuce il volume.

uso:  python3 build/impagina.py stampa    # folii + testatine, scrive build/indice.json
      python3 build/impagina.py unisci    # preliminari + capitoli -> PDF finale
"""
import io, json, os, sys
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(RADICE, 'build')
FONT = os.path.join(RADICE, 'stile', 'font')
LIBRO = json.load(open(os.path.join(RADICE, 'libro.json'), encoding='utf-8'))

LARGH, ALTEZ = 170 * mm, 240 * mm
GRIGIO = (0.38, 0.34, 0.29)
INCHIOSTRO = (0.13, 0.11, 0.09)

pdfmetrics.registerFont(TTFont('Mono', os.path.join(FONT, 'IBM-Plex-Mono-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Slab', os.path.join(FONT, 'Zilla-Slab-Medium.ttf')))


def sovrapposizione(pagine):
    """pagine: lista di (folio, testatina|None). None = pagina di apertura, non si timbra."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(LARGH, ALTEZ))
    for folio, testa in pagine:
        if testa is not None:
            recto = folio % 2 == 1
            c.setFont('Mono', 7.2)
            c.setFillColorRGB(*GRIGIO)
            if recto:
                c.drawRightString(LARGH - 17 * mm, ALTEZ - 12 * mm, testa)
            else:
                c.drawString(17 * mm, ALTEZ - 12 * mm, LIBRO['titolo'])
            c.setLineWidth(0.3)
            c.setStrokeColorRGB(*GRIGIO)
            c.line(17 * mm, ALTEZ - 14.6 * mm, LARGH - 17 * mm, ALTEZ - 14.6 * mm)
            c.setFont('Mono', 8.4)
            c.setFillColorRGB(*INCHIOSTRO)
            c.drawCentredString(LARGH / 2, 11 * mm, str(folio))
        c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def stampa():
    indice, folio = {}, 1
    for cap in [c for c in LIBRO['capitoli'] if c.get('file')]:
        sorgente = os.path.join(BUILD, 'cap%s.pdf' % cap['id'])
        if not os.path.exists(sorgente):
            print('  manca', sorgente); continue
        lettore = PdfReader(sorgente)
        indice[cap['id']] = folio
        testatina = '%s · %s' % (cap['id'], cap['titolo'])
        descr = [(folio + i, None if i == 0 else testatina) for i in range(len(lettore.pages))]
        strato = sovrapposizione(descr)
        scrittore = PdfWriter()
        for i, pagina in enumerate(lettore.pages):
            pagina.merge_page(strato.pages[i])
            scrittore.add_page(pagina)
        uscita = os.path.join(BUILD, 'cap%s-f.pdf' % cap['id'])
        with open(uscita, 'wb') as f:
            scrittore.write(f)
        print('  cap %s: pagine %d-%d (%d)' % (cap['id'], folio, folio + len(lettore.pages) - 1, len(lettore.pages)))
        folio += len(lettore.pages)
    json.dump(indice, open(os.path.join(BUILD, 'indice.json'), 'w'), indent=1)
    print('  indice:', indice)


def unisci():
    scrittore = PdfWriter()
    prelim = os.path.join(BUILD, 'preliminari.pdf')
    if os.path.exists(prelim):
        for p in PdfReader(prelim).pages:
            scrittore.add_page(p)
    for cap in [c for c in LIBRO['capitoli'] if c.get('file')]:
        f = os.path.join(BUILD, 'cap%s-f.pdf' % cap['id'])
        if os.path.exists(f):
            for p in PdfReader(f).pages:
                scrittore.add_page(p)
    scrittore.add_metadata({'/Title': LIBRO['titolo'], '/Subject': LIBRO['sottotitolo'], '/Creator': 'filiera libro/'})
    uscita = os.path.join(RADICE, 'Falegnameria-passo-a-passo.pdf')
    with open(uscita, 'wb') as f:
        scrittore.write(f)
    print('  %s · %d pagine · %.1f MB' % (os.path.basename(uscita), len(scrittore.pages), os.path.getsize(uscita) / 1e6))


if __name__ == '__main__':
    {'stampa': stampa, 'unisci': unisci}[sys.argv[1]]()
