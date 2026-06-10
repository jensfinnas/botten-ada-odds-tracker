# Design: botten-ada-odds-tracker

**Datum:** 2026-06-10
**Status:** Godkänd av Jens 2026-06-10

## Syfte

Dagligen samla in odds/priser om riksdagsvalet 2026 (valdag 13 september) från
vadslagningssajter och prediktionsmarknader, spara rådata i repot, och
sammanställa harmoniserade sannolikheter per fråga i cleana CSV-filer — så att
marknadernas implicita sannolikheter kan jämföras med Botten Adas
modellberäknade sannolikheter över tid.

Repot är publikt, gratis att driva (GitHub Actions på publikt repo) och
transparent dokumenterat i README (engelska).

## Källor (v1)

| Källa | Typ | API | Anteckning |
|---|---|---|---|
| `botten_ada` | Prognosmodell | `http://ada-site-data.s3.eu-north-1.amazonaws.com/latest_forecast/question--<Q_ID>.json` | Sannolikheter direkt (`questions.<id>.now.prob`) |
| `kambi` | Bokmakare | `https://eu-offering-api.kambicdn.com/offering/v2018/ub/...` | Driver Unibet, Svenska Spel Oddset, ATG och Paf — identiska odds, räknas som EN källa. Event-ID återupptäcks varje körning via `listView/politics.json`. Offering-nycklarna `svenskaspel`/`atg`/`paf` är redundans om `ub` blockeras. |
| `betsson` | Bokmakare | `https://www.betsson.com/api/sb/v1/widgets/view/v1?...` | Kräver statiska custom headers (brandid, x-sb-jurisdiction: Sga m.fl.). Oberoende prissättning. Risk: jurisdiktionsfiltrering från US-datacenter-IP. |
| `smarkets` | Börs | `https://api.smarkets.com/v3/...` | Officiellt publikt API. Back/lay-priser i sannolikhets-baspunkter. Tunn likviditet. |
| `polymarket` | Prediktionsmarknad | `https://gamma-api.polymarket.com/events?slug=<slug>` | Priser är sannolikheter direkt. |

Medvetet bortvalda: Bet365 (anti-bot), Betfair/William Hill (geo-block/lämnat
Sverige), Pinnacle/bwin/Coolbet (saknar marknader), oddschecker/oddsportal
(Cloudflare/JS). Kalshi har svenskt event men inga priser/likviditet —
kandidat att lägga till senare.

## Arkitektur

En daglig GitHub Actions-körning (cron ~05:00 UTC) i tre steg, resultatet
committas till repot:

1. **Scrape** — en scraper per källa hämtar ALLA marknader den hittar om
   riksdagsvalet och appendar dagens observation till en JSON-fil per marknad
   i `data/raw/<källa>/`.
2. **Harmonisera + sammanställ** — clean-CSV:erna byggs om från grunden ur
   rådatan varje körning (idempotent: metodändringar räknar om historiken).
3. **Commit + push** om något ändrats.

```
botten-ada-odds-tracker/
├── scrapers/
│   ├── __init__.py      # registry: SCRAPERS = {"kambi": ..., ...}
│   ├── base.py          # gemensamt interface + raw-filhantering (append)
│   ├── botten_ada.py
│   ├── kambi.py
│   ├── betsson.py
│   ├── smarkets.py
│   └── polymarket.py
├── pipeline/
│   ├── mappings.yaml    # källmarknad → fråga; hjärtat i systemet
│   ├── harmonize.py     # odds → sannolikheter per källtyp
│   └── build_clean.py   # raw + mappings → data/clean/*.csv + QUESTIONS.md
├── run.py               # CLI: python run.py [--source X]... [--skip-clean] [--skip-scrape]
├── data/
│   ├── raw/{botten_ada,kambi,betsson,smarkets,polymarket}/<marknadsslug>.json
│   └── clean/<question_id>.csv  (+ QUESTIONS.md, genererad)
├── tests/               # pytest, fixtures = sparade API-svar
└── .github/workflows/scrape.yml
```

**Designprincip:** scrapers är dumma. De känner inte till Ada-ontologin utan
sparar marknader under en stabil källspecifik slug och i källans eget
oddsformat. All mappning till frågor sker centralt i `mappings.yaml`. Nya
marknader hos en källa fångas automatiskt i raw; att exponera dem i clean är
en rad i mappningsfilen, ingen scraperkod.

## Raw-format

En JSON-fil per (källa, marknad). Filnamn: stabil slug ur källans egen
marknadsbenämning. Observationer appendas — en per datum (körs scrapern två
gånger samma dag ersätts dagens observation, ingen dubblett).

```json
{
  "source": "kambi",
  "market_name": "Party/Coalition to obtain most seats",
  "market_id": "1020265650/2351720973",
  "url": "https://www.unibet.se/betting/sports/...",
  "odds_format": "decimal",
  "observations": [
    {
      "date": "2026-06-10",
      "fetched_at": "2026-06-10T05:01:13Z",
      "outcomes": [
        {"label": "(S)+(V)+(MP)+(C)", "odds": 1.22},
        {"label": "(M)+(SD)+(KD)+(L)", "odds": 3.75}
      ]
    }
  ]
}
```

Per källa gäller:

- `kambi`/`betsson`: `odds_format: "decimal"`, decimalodds som publicerade.
  O/U-marknader får `line`-fält på utfallet (procent, t.ex. `4.0`).
- `smarkets`: `odds_format: "smarkets_quotes"`, bid/offer i baspunkter som
  API:t levererar.
- `polymarket`: `odds_format: "probability"`, Yes/No-priser 0–1 samt
  bestBid/bestAsk.
- `botten_ada`: `odds_format: "probability"`, prob 0–1 + metadata om
  modellkörning.

Botten Ada-rådata sparas i samma observationsformat (en fil per fråga,
`prob` som utfall) så att hela pipelinen är enhetlig.

## Harmonisering: odds → sannolikhet

Målet är rättvist jämförbara sannolikheter. Metod per källtyp,
dokumenterad i README:

- **Bokmakare (decimalodds):** implicit sannolikhet `1/odds` summerar över
  marknadens utfall till mer än 1 — överskottet (overround) är bokmakerns
  marginal. Marginalen tas bort med **proportionell normalisering**:
  `p_i = (1/odds_i) / Σ_j (1/odds_j)` över marknadens samtliga utfall.
  Standardmetod, transparent, exakt för tvåvägsmarknader. Känd svaghet:
  favourite-longshot-bias i flervalsmarknader; Shins metod är möjlig
  framtida förbättring och nämns i README.
- **Smarkets (börs):** priser saknar inbakad marginal (avgift tas på vinst).
  Sannolikhet = mittpunkt av implicit back- och lay-sannolikhet
  (API:ts baspunkter / 10000). Ingen normalisering över utfallen — varje
  kontrakt prissätts oberoende på börsen och tunna böcker skulle förvrängas
  av normalisering. Saknas bid eller offer → ingen observation den dagen.
- **Polymarket:** priserna är sannolikheter. Midpoint av bestBid/bestAsk
  när båda finns, annars `outcomePrices`.
- **Botten Ada:** `prob` används direkt.

Multivalsmarknader (t.ex. "största parti", 8 utfall) normaliseras över alla
utfall; varje binär fråga tar sedan sitt utfalls `p` (frågan "vinner S?" får
`p_S`).

## Frågemappning och ontologi

Clean-frågor är **binära** och namnges enligt Botten Adas question-ontologi
(`botten-ada-data-preparation/PROB_QUESTIONS.md`). Marknader utan
Ada-motsvarighet får nya nycklar i samma namnstil, markerade
`in_ada_ontology: false` i mappningen (kandidater att lägga till i Ada).

Mappningar vid start:

| Fråga | Ada | Kambi | Betsson | Smarkets | Polymarket |
|---|---|---|---|---|---|
| `does_lw_get_more_seats_than_rw` | ✓ | ✓ (blockduell) | ✓ | – | – |
| `does_rw_get_more_seats_than_lw` | ✓ | ✓ (samma marknad, andra utfallet) | ✓ | – | – |
| `does_M_L_KD_SD_have_seat_majority` | ✓ | – | – | – | ✓ (Tidö-marknaden) |
| `is_SD_larger_than_M` / `is_M_larger_than_SD` | ✓ | ✓ (H2H flest röster) | – | – | – |
| `is_L_above_4_pct` | ✓ | ✓ (O/U-linje 4,0) | ✓ (O/U-linje 4,0) | – | – |
| `does_<P>_get_most_votes` (8 partier) | nya nycklar | ✓ | ✓ | – | – |
| `does_<P>_get_most_seats` (per parti) | nya nycklar | – | – | ✓ | ✓ |
| `does_<kandidat>_become_pm` (per kandidat) | nya nycklar | ✓ | ✓ | ✓ | ✓ |

**Linjevillkor:** O/U-marknader mappas mot `is_<P>_above_4_pct` endast när
linjen är exakt 4,0 (idag bara L). Mappningsposten anger förväntad linje;
flyttas linjen bryts mappningen automatiskt (värdet utelämnas + varning) i
stället för att förorena serien. Samma princip för utfallsetiketter: posten
anger exakt förväntad etikett, ändrade etiketter ger varning, inte fel data.

Anteckning om semantik: "flest mandat"-blockduellen hos Kambi/Betsson är en
tvåvägsmarknad utan oavgjort-utfall; Botten Adas `does_lw_get_more_seats_than_rw`
och spegelfrågan hanterar lika-mandat separat, så marknadens p respektive 1−p
mappas till respektive fråga. Skillnaden (sannolikheten för exakt lika) är
försumbar men nämns i QUESTIONS.md.

`mappings.yaml`-postens form:

```yaml
- question_id: is_L_above_4_pct
  in_ada_ontology: true
  sources:
    kambi:
      market_slug: percentage_of_votes_obtained_by_liberalerna
      outcome_label: "Over"
      require_line: 4.0
    betsson:
      market_slug: riksdagsvalet_2026_procent_av_rosterna_l
      outcome_label: "Över"
      require_line: 4.0
```

## Clean-format

`data/clean/<question_id>.csv`, en rad per datum, sannolikheter som andelar
0–1, kolumner = källor (fast ordning: botten_ada först, övriga alfabetiskt):

```csv
date,botten_ada,betsson,kambi,polymarket,smarkets
2026-06-10,0.971,0.965,0.962,,
```

Tom cell = källan saknade marknaden/observationen den dagen.

`data/clean/QUESTIONS.md` genereras vid varje körning: per fråga visas
beskrivning, om den ingår i Ada-ontologin, samt exakt marknadsformulering och
URL per källa.

## Körning och schemaläggning

- `run.py` kör alla scrapers (eller `--source kambi` för en), därefter
  clean-bygget. Exit-kod 0 om minst en källa lyckades; per-källa-fel loggas
  och skrivs till workflow-sammanfattningen.
- GitHub Actions: cron `0 5 * * *` + `workflow_dispatch` för manuell körning.
  Steg: checkout → setup-python → `pip install -r requirements.txt` →
  `python run.py` → commit/push vid diff (`github-actions[bot]`).
- Misslyckas en källa N dagar i rad syns det i Actions-loggen; inga
  notifieringar i v1.

## Felhantering

- Varje scraper failar isolerat; övriga körs klart och committas.
- Nätverksanrop: timeout 30 s, 3 försök med backoff.
- Valideringar: odds > 1.0 (decimal), sannolikheter i [0,1],
  mappade marknader måste matcha förväntad etikett/linje.
- **Betsson-risken:** headers kan ruttna och jurisdiktionsfiltrering kan ge
  tomma svar från US-runners. Testas i första Actions-körningen; vid fel blir
  kolumnen tom och källan utvärderas (tas bort eller åtgärdas) — den får inte
  blockera övriga.

## Teknik och kvalitet

- Python 3.12; beroenden: `requests`, `pyyaml` (+ `pytest` för test).
  Ingen browser/headless — alla källor är rena JSON-API:er.
- Tester: pytest med sparade API-svar som fixtures; täcker parsning per
  scraper, harmonisering (kända odds → kända sannolikheter), mappnings-
  validering och CSV-bygget. Inga nätverksanrop i test.
- Licens: MIT. README på engelska: syfte, källor, metod (harmonisering med
  formler), dataformat, begränsningar/biaser, hur man lägger till källa/fråga.

## Utanför scope (v1)

- Kalshi, Manifold, Metaculus, Bet365.
- Notifieringar vid källfel.
- Shins metod för vig-removal.
- Visualisering/grafer.
