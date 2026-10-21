# Argent0rum projekti

Visas manas vietnes vienā vietā: **https://argent0rum.github.io/**

## Kā tas darbojas

- Lapa pati paprasa GitHub, kuriem repozitorijiem ir ieslēgts **GitHub Pages**, un parāda tos kā kartītes.
  Tātad, kad tiek izveidota jauna vietne, tā šeit parādās **automātiski**, neko nemainot.
- Katru rītu GitHub Actions saglabā sarakstu failā `dati/repos.json` (lai lapa atveras uzreiz) un
  uztaisa priekšskatījuma attēlu jaunām vietnēm mapē `atteli/`.

## Kā mainīt nosaukumu vai aprakstu

Atver `projekti.json` (GitHub lapā → zīmulīša ikona) un pievieno vai labo ierakstu:

```json
{
  "repo": "repozitorija-nosaukums",
  "lv": { "nosaukums": "Nosaukums latviski", "apraksts": "Īss apraksts latviski." },
  "en": { "nosaukums": "Name in English", "apraksts": "Short description in English." },
  "birkas": ["dati", "mācības"],
  "atjauno": "dienā"
}
```

- `birkas` — filtri lapas augšā (var izdomāt jaunas).
- `atjauno` — neobligāts: `"dienā"` vai `"mēnesī"`, ja vietnes dati atjaunojas paši.
- Ja vietnei ieraksta nav, lapa izmanto repozitorija aprakstu (GitHub → repozitorijs → ⚙ blakus "About").

## Kā paslēpt vietni

Ieliec repozitorija nosaukumu sarakstā `"slept"` failā `projekti.json`.

## Kā pievienot vietni, kas nav GitHub

Pievieno ierakstu ar `"url"` repo vietā, piemēram `{"url": "https://...", "lv": {...}, "en": {...}}`.

## Attēli

Attēls tiek uztaisīts automātiski vienu reizi. Lai to atjaunotu, izdzēs `atteli/<repo>.jpg` —
nākamajā rītā (vai palaižot Actions → "Atjaunot projektu sarakstu") tiks uztaisīts jauns.
