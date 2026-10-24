/* Impagina le unità del libro in PDF con Chromium.
   uso:  node build/costruisci.js capitoli | preliminari | tutto        */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RADICE = path.resolve(__dirname, '..');
const libro = JSON.parse(fs.readFileSync(path.join(RADICE, 'libro.json'), 'utf8'));
const stile = (f) => 'file://' + path.join(RADICE, 'stile', f);

function figura(nome) {
  const f = path.join(RADICE, 'figure', nome + '.html');
  if (!fs.existsSync(f)) throw new Error('figura mancante: ' + nome);
  return fs.readFileSync(f, 'utf8');
}

function apertura(cap) {
  const img = path.join(RADICE, 'immagini', `cap${cap.id}-apertura.png`);
  const lastra = fs.existsSync(img)
    ? `<img src="file://${img}" alt="">`
    : `<div class="attesa">apertura fotografica del capitolo ${cap.id}<br>immagine generata, in attesa dei file<br>(16:9 · 2048 px · fondo da inserire in fase di stampa)</div>`;
  return `<div class="apertura">
  <div class="lastra">${lastra}</div>
  <div class="numero">Capitolo ${cap.id}</div>
  <h1>${cap.titolo}</h1>
  <p class="sommario">${cap.sommario}</p>
  ${cap.dati ? `<div class="riga-dati">${cap.dati.map(d => `<span>${d}</span>`).join('')}</div>` : ''}
</div>`;
}

function risolvi(html, cap) {
  return html
    .replace(/\{\{\s*fig:([a-z0-9-]+)\s*\}\}/gi, (_, n) => figura(n))
    .replace(/\{\{\s*apertura\s*\}\}/gi, () => apertura(cap));
}

function documento(corpo) {
  return `<!doctype html><html lang="it"><head><meta charset="utf-8">
<link rel="stylesheet" href="${stile('font-locali.css')}">
<link rel="stylesheet" href="${stile('stampa.css')}">
</head><body>${corpo}</body></html>`;
}

function preliminari() {
  let indice = {};
  const fi = path.join(RADICE, 'build', 'indice.json');
  if (fs.existsSync(fi)) indice = JSON.parse(fs.readFileSync(fi, 'utf8'));

  let parte = null;
  const voci = libro.capitoli.map((c) => {
    let testa = '';
    if (c.parte !== parte) { parte = c.parte; testa = `<div class="gruppo">${parte}</div>`; }
    const p = indice[c.id] ? indice[c.id] : '—';
    return `${testa}<div class="voce"><span class="n">${c.id}</span><span class="t">${c.titolo}<em>${c.sommario}</em></span><span class="p">${p}</span></div>`;
  }).join('');

  const oggi = new Date().toLocaleDateString('it-IT', { year: 'numeric', month: 'long', day: 'numeric' });

  return documento(`
<section class="pagina occhio">
  <div class="filetto"></div>
  <h1>${libro.titolo}</h1>
  <p class="sotto">${libro.sottotitolo}</p>
  <p class="colofone">${libro.edizione}</p>
</section>

<section class="pagina">
  <h2 class="sezione">Come si usa questo libro</h2>
  <p>Ogni capitolo è costruito nello stesso modo, perché in bottega si impara ripetendo una procedura, non leggendo una materia. Prima gli attrezzi necessari e le avvertenze di sicurezza, poi le operazioni numerate: una per volta, nell'ordine in cui vanno eseguite, ciascuna con il disegno quotato di quello che devi ottenere e, dove serve, l'errore tipico con il suo rimedio accanto.</p>
  <p>Alla fine di ogni capitolo c'è un test in tre parti. La <b>parte A</b> verifica le conoscenze con domande a scelta multipla. La <b>parte B</b> sono calcoli di bottega: spessori, lunghezze di taglio, quote del truschino, gli stessi conti che faresti davanti al banco. La <b>parte C</b> è la più importante: ti viene descritto un difetto e devi elencare <em>tutte</em> le cause possibili, come riconoscerle sul pezzo e il rimedio per ciascuna. È il modo in cui lavora un falegname esperto — non "questo non va", ma "questo non va per uno di questi sei motivi, e si vede da qui".</p>
  <p>Le soluzioni seguono ogni test e non sono una semplice chiave: ogni risposta è accompagnata dal motivo tecnico, perché la regola si ricorda e la risposta no.</p>
  <h3 style="margin-top:6mm">Convenzioni</h3>
  <p>Tutte le quote sono in millimetri. Le tolleranze indicate valgono per legni duri europei — frassino, rovere, faggio — a un'umidità del 9–11%, cioè legno acclimatato in ambiente riscaldato. Nei disegni il tratteggio indica le superfici di incollaggio o il materiale di scarto, secondo la didascalia; la linea in colore indica la tracciatura o il gesto in corso.</p>
  <div class="scheda sicurezza" style="margin-top:6mm">
    <h3>Avvertenza</h3>
    <ul>
      <li>Le lavorazioni descritte si eseguono con utensili affilati: il pezzo va sempre fermato in morsa o contro un fermo prima di applicare forza.</li>
      <li>Le procedure sono scritte per il lavoro a mano. Dove compare un utensile elettrico, le protezioni del costruttore non vanno rimosse per nessun motivo.</li>
      <li>Prova sempre un giunto nuovo su due ritagli della stessa essenza prima di eseguirlo sul pezzo definitivo.</li>
    </ul>
  </div>
</section>

<section class="pagina indice">
  <h2 class="sezione">Indice</h2>
  ${voci}
  <p class="colofone" style="margin-top:7mm">I capitoli senza numero di pagina sono in lavorazione in questa bozza. Aggiornato al ${oggi}.</p>
</section>`);
}

(async () => {
  const quale = process.argv[2] || 'tutto';
  fs.mkdirSync(path.join(RADICE, 'build'), { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const opzioni = { preferCSSPageSize: true, printBackground: true };

  const rendi = async (html, uscita) => {
    // il documento va servito da disco: Chromium rifiuta le risorse file://
    // richieste da una pagina senza URL proprio (setContent).
    const temporaneo = uscita.replace(/\.pdf$/, '.html');
    fs.writeFileSync(temporaneo, html, 'utf8');
    await page.goto('file://' + temporaneo, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({ ...opzioni, path: uscita });
    console.log('  →', path.basename(uscita));
  };

  if (quale === 'capitoli' || quale === 'tutto') {
    for (const c of libro.capitoli.filter((c) => c.file && fs.existsSync(path.join(RADICE, c.file)))) {
      const sorgente = fs.readFileSync(path.join(RADICE, c.file), 'utf8');
      console.log('capitolo', c.id, c.titolo);
      await rendi(documento(risolvi(sorgente, c)), path.join(RADICE, 'build', `cap${c.id}.pdf`));
    }
  }
  if (quale === 'preliminari' || quale === 'tutto') {
    console.log('preliminari');
    await rendi(preliminari(), path.join(RADICE, 'build', 'preliminari.pdf'));
  }
  await browser.close();
})();
