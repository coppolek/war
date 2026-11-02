# Riviera Gunship — versione multipiattaforma

Gioco web (PWA) + server di stanze. Funziona da browser su PC, Mac, telefono, tablet e console con browser;
su telefono si può installare come app ("Aggiungi a schermata Home"). Fino a 6 piloti per stanza, cross-play totale.

## Cosa c'è
- `public/` — il gioco (index.html, manifest, service worker, icone)
- `server/server.js` — server Node: serve il gioco e gestisce le stanze via WebSocket (`/ws`), matchmaking rapido, relay eventi, anti-flood
- `Dockerfile`, `docker-compose.yml` — avvio con Docker
- `build.py` — rigenera `public/index.html` dal sorgente del gioco (`python3 build.py ../dune-gunship.html`)

## Prova in locale
```bash
cd server && npm install && node server.js      # poi apri http://localhost:8080
```
Apri due schede, premi **2** (Multiplayer) in entrambe: finite nella stessa stanza.
Stanza privata con amici: `https://TUO-DOMINIO/?r=NOMESTANZA` (il pulsante "Copia link invito" nella lobby lo fa da solo).

## Deploy sul VPS (Docker + Nginx Proxy Manager)
1. Copia la cartella sul VPS (es. `/opt/riviera-gunship`) e avvia:
   ```bash
   cd /opt/riviera-gunship && docker compose up -d --build
   curl localhost:8085/health          # -> {"ok":true,...}
   ```
   Alternativa dal pannello Hostinger (Docker Manager > Componi > Componi manualmente): carica il contenuto della cartella su un repository GitHub pubblico e incolla:
   ```yaml
   services:
     riviera:
       build: https://github.com/TUOUTENTE/riviera-gunship.git
       container_name: riviera-gunship
       restart: unless-stopped
       ports:
         - "8085:8080"
   ```
   (il Dockerfile deve stare nella radice del repository)
   ```bash
   ```
2. DNS: crea un record A `riviera.puulp.it` verso l'IP del VPS.
3. Nginx Proxy Manager → Proxy Hosts → Add:
   - Domain: `riviera.puulp.it` · Forward host `172.17.0.1` (IP del docker host) · porta `8085`
   - **Attiva "Websockets Support"** (indispensabile per il multiplayer)
   - Tab SSL: richiedi Let's Encrypt, attiva Force SSL
4. Apri `https://riviera.puulp.it` da telefono e PC: premi 2 e giocate insieme.

Opzionale: in `docker-compose.yml` decommenta `ALLOWED_ORIGINS` per accettare solo il tuo dominio.

## Aggiornare il gioco
Dopo ogni modifica al sorgente: `python3 build.py <sorgente.html>`, poi sul VPS `docker compose up -d --build`.
(Il service worker aggiorna da solo i client; in caso di cache testarda cambia `V` in `public/sw.js`.)

## Mappe reali da OpenStreetMap (strumento `tools/osm2rg.py`)
Il gioco parte con una Rimini *schematica*. Per usare una città vera, genera il file mappa con lo script
(solo Python 3, nessuna libreria; Pillow opzionale per l'anteprima). Va lanciato da un computer o dal VPS con
accesso a internet normale (i server Overpass di OpenStreetMap devono essere raggiungibili).
```bash
cd tools
# 1) scarica e converti Rimini (3,6 x 3,6 km attorno al centro) -> public/maps/rimini.js
python3 osm2rg.py --name rimini --title Rimini --center 44.0627,12.5683 --out ../public/maps/rimini.js --preview rimini.png
# 2) altre città: stesso comando con un altro nome e centro
python3 osm2rg.py --name milano --title Milano --center 45.4642,9.1900  --out ../public/maps/milano.js
python3 osm2rg.py --name roma   --title Roma   --center 41.8986,12.4768 --out ../public/maps/roma.js
# 3) rigenera il gioco e riavvia
cd .. && python3 build.py ../dune-gunship.html && docker compose up -d --build
```
- Se il download fallisce o è troppo grande: apri overpass-turbo.eu, esegui la query, esporta "dati grezzi (JSON)" e usa `--input file.json`.
- `public/maps/rimini.js`, se presente, sostituisce la Rimini schematica. Le altre città si aprono con `?m=milano`
  (il link d'invito della lobby lo include da solo). Tutti i giocatori di una stanza devono usare la stessa mappa.
- `--tile-m 30` = metri per tile (mappa 120x120 tile). Più piccolo = più dettaglio e area più piccola. `--base LAT,LON` fissa l'eliporto.
- Il convertitore trasforma: coste/mare, fiumi, strade (con ponti), edifici (altezza dai piani OSM), parchi, spiagge, ferrovie, aeroporto.
  Gli edifici sono approssimati a rettangoli. Le missioni usano gli stessi nomi di Rimini anche su altre città (testi personalizzabili in seguito).
- `tools/esempio/` contiene dati di prova sintetici usati per collaudare lo strumento (non sono dati reali).

## Limiti attuali (onesti)
- Il server è un relay: non c'è account/login, classifiche o anti-cheat. Ogni client simula i nemici come nel co-op attuale (l'host sincronizza i mezzi mobili).
- Un solo processo Node: regge decine di stanze; per migliaia di giocatori servirebbe scalare in più istanze.
- Le mappe sono la sola Rimini; altre città si aggiungono come nuove funzioni di generazione.
