# Innova Ducto M7 per Home Assistant

Controlla i ventilconvettori **Innova Ducto con termostato M7 Wi-Fi** direttamente da Home Assistant, attraverso il cloud Innova di nuova generazione.

Questa integrazione nasce dall'esigenza di collegare i dispositivi M7 all'impianto domotico dopo il cambiamento delle API dell'app ufficiale. Il protocollo è stato ricostruito analizzando l'app Android **Innova 3.1.3 (165)** e verificato progressivamente su un impianto reale.

**Versione attuale: 0.1.4 — integrazione non ufficiale, in sviluppo.**

## Funzionalità

- Rilevamento del dispositivo tramite account Innova e MAC Wi-Fi.
- Recupero automatico del nome assegnato nell'app e del nodo del dispositivo.
- Visualizzazione della temperatura ambiente e del setpoint.
- Sensore di umidità, quando disponibile.
- Accensione e spegnimento.
- Modalità caldo, freddo, ventilazione e automatico, secondo le capacità del dispositivo.
- Velocità ventola **Turbo, Max, Medio, Min e Auto**.
- Preset **Manuale** e **Calendario**.
- Passaggio a Manuale prima di modificare la temperatura da Home Assistant.
- Aggiornamento dei dati ogni 60 secondi e dopo i comandi.
- Icona e logo Innova inclusi.
- Diagnostica senza credenziali, token o identificativi della casa.

## Compatibilità e verifiche

L'integrazione è destinata ai **Ducto con comando M7 Wi-Fi** associati all'app Innova recente.

La lettura dello stato e i comandi base sono stati confermati su un M7 identificato dal cloud con `vendorId: 1`, `productId: 2002` e `hwRevision: 1`. Il nome del dispositivo, temperatura, setpoint e umidità vengono letti correttamente. Con il calendario disabilitato nell'app, il dispositivo accetta le impostazioni inviate da Home Assistant.

Il codice include parser per le famiglie cloud **fancoil** e **thermostat**. Questo non costituisce una conferma di compatibilità con tutti i prodotti Innova.

I preset Manuale/Calendario e il comando Turbo sono implementati sulla base delle definizioni dell'APK e verificati con test locali; il collaudo completo di queste funzioni sui diversi modelli è ancora in corso.

## Requisiti

- Home Assistant **2026.3 o successivo** come versione minima prevista, anche per le immagini del marchio locali. Le prove sull'impianto sono state effettuate con Home Assistant 2026.9.
- Account Innova con accesso tramite **email e password**.
- Dispositivo già associato e funzionante nell'app ufficiale.
- MAC Wi-Fi del dispositivo.
- Connessione Internet disponibile sia per Home Assistant sia per il dispositivo.

L'accesso tramite Google/OAuth non è implementato. L'integrazione utilizza il cloud: non offre controllo locale né Bluetooth.

## Installazione tramite HACS

Il repository può essere aggiunto a HACS come **repository personalizzato**:

1. Apri **HACS → Integrazioni**.
2. Dal menu in alto a destra scegli **Repository personalizzati**.
3. Inserisci `https://github.com/markdade80/innovaductom7`.
4. Seleziona la categoria **Integrazione** e aggiungi il repository.
5. Cerca **Innova Ducto M7** in HACS e installalo.
6. Riavvia Home Assistant.
7. Apri **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Innova Ducto M7**.

Il repository non è ancora incluso nell'elenco HACS predefinito: fino all'eventuale approvazione pubblica va aggiunto come repository personalizzato.

## Installazione manuale

1. Scarica ed estrai il pacchetto dell'integrazione.
2. Copia la cartella `innova_ducto_m7`, contenuta in `custom_components`, nella directory `custom_components` della configurazione di Home Assistant.
3. Controlla che il percorso del manifest sia esattamente:

   ```text
   /config/custom_components/innova_ducto_m7/manifest.json
   ```

4. Riavvia Home Assistant.
5. Apri **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**.
6. Cerca **Innova Ducto M7**.
7. Inserisci email, password e MAC Wi-Fi.
8. Lascia vuoto il campo **Nodo** per il rilevamento automatico. Se il cloud restituisce più nodi per lo stesso MAC, specifica quello da configurare.

Ripeti la configurazione per aggiungere un altro dispositivo o nodo.

## Utilizzo

L'integrazione crea un'entità `climate` con il nome assegnato nell'app Innova e un sensore di umidità.

### Temperatura e programmazione

Il calendario Innova può ripristinare il setpoint programmato dopo un comando manuale. Per questo, quando si modifica la temperatura da Home Assistant, l'integrazione attiva prima **Manuale** e verifica il nuovo stato prima di inviare il setpoint.

Il preset **Calendario** disattiva la forzatura manuale del nodo e restituisce il controllo alla programmazione esistente. Non riscrive gli orari del calendario.

Se il passaggio a Manuale non viene confermato subito, Home Assistant mostra un errore e invita a riprovare: la temperatura non viene inviata dichiarando un successo non verificato.

### Ventilazione

Le velocità disponibili nell'interfaccia sono:

| Velocità | Codice del protocollo |
| --- | --- |
| Turbo | BOOST — 5 |
| Max | MAX — 4 |
| Medio | MID — 3 |
| Min | MIN — 2 |
| Auto | AUTO — 1 |

La disponibilità effettiva delle funzioni dipende dal dispositivo. Le capacità non vengono ancora usate per filtrare tutte le opzioni mostrate nell'interfaccia.

## Aggiornamento

Se l'integrazione è stata installata tramite HACS, gli aggiornamenti vengono proposti direttamente da HACS. Con installazione manuale, sostituisci i file della cartella `custom_components/innova_ducto_m7` con quelli della nuova versione e riavvia Home Assistant. Mantieni la configurazione esistente: non occorre reinserire le credenziali.

Il dominio `innova_ducto_m7` è distinto da `innova_duepuntozero`: l'integrazione può essere installata senza sovrascrivere quel componente.

**Aggiornamento alla 0.1.4:** nelle eventuali automazioni, i vecchi nomi `auto`, `low`, `medium`, `high` devono essere sostituiti rispettivamente con `Auto`, `Min`, `Medio`, `Max`.

## Diagnostica e problemi comuni

- **Accesso fallito:** controlla le credenziali e che l'account utilizzi email/password. Il messaggio diagnostico distingue gli errori HTTP dal mancato rilevamento del dispositivo.
- **MAC non trovato:** verifica che sia il MAC Wi-Fi e che il dispositivo appartenga all'account utilizzato.
- **Più nodi per lo stesso MAC:** specifica il nodo nella configurazione.
- **Configurazione in attesa o dispositivo non disponibile:** controlla Internet, lo stato nell'app Innova e la motivazione mostrata da Home Assistant.
- **Temperatura ripristinata dal calendario:** verifica il preset attivo e il passaggio a Manuale.
- **Umidità sconosciuta:** il dispositivo potrebbe non fornire questa misura.

Nei registri cerca `custom_components.innova_ducto_m7`. Dalla pagina dell'integrazione puoi scaricare la diagnostica, quando disponibile. Il registro sintetico degli errori non contiene necessariamente i messaggi di livello debug: l'assenza di una voce non dimostra che non sia partita una richiesta.

Per segnalare un problema, indica versione di Home Assistant, versione dell'integrazione, modello del comando, operazione effettuata e messaggio di errore. Non pubblicare password, token o configurazioni complete di Home Assistant.

## Dettagli tecnici

L'integrazione utilizza:

- REST v2 su `v2.api.innova.solutiontech.tech` per autenticazione e rilevamento dei dispositivi.
- gRPC su `v2.grpc.innova.solutiontech.tech` tramite il servizio `services.app.AppService`.
- Il metodo `SendDevice` per ottenere lo stato completo dei nodi e inviare comandi.
- Protobuf con codifica e decodifica in Python e trasporto HTTP/2 tramite `h2`.

Lo stato completo e gli eventi incrementali del protocollo hanno strutture differenti. La versione attuale aggiorna i dati tramite richieste periodiche dello stato completo.

## Versioni

| Versione | Modifiche principali |
| --- | --- |
| 0.1.4 | Turbo e nomi delle velocità allineati all'app ufficiale. |
| 0.1.3 | Preset Manuale/Calendario, passaggio a Manuale prima del setpoint e arrotondamento dell'umidità. |
| 0.1.2 | Lettura corretta dello stato completo restituito da `SendDevice`; prima conferma sull'impianto. |

## Riconoscimenti

Il progetto [Home Assistant Innova Duepuntozero di Christoph Hohner](https://github.com/ChristophHohner/homeassistant-innova-duepuntozero) è stato un riferimento iniziale per l'analisi del precedente protocollo cloud.

Questa integrazione non è affiliata, approvata o supportata da Innova. Nome, icona e logo Innova appartengono ai rispettivi titolari e sono usati per identificare i dispositivi compatibili.
