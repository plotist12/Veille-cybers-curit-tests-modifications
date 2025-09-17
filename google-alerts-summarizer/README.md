# Google Alerts → Résumés quotidiens (gratuit)

Ce petit projet récupère un **flux RSS Google Alerts** (ex: *cybersécurité*), télécharge chaque article et génère un **résumé automatique** en français (méthode extractive TextRank, pas d'API payante). Un rapport **Markdown** est créé chaque jour dans `./output/`.

## 🚀 Démarrage rapide (local)
1) Installez Python 3.10+.
2) Dans un terminal, installez les dépendances :
```bash
pip install -r requirements.txt
```
3) Récupérez l’URL **RSS** de votre alerte Google :
   - Allez sur [Google Alerts](https://www.google.com/alerts)
   - Créez/éditez une alerte → **Afficher les options** → *Livrer à* : **Flux RSS** → *Créer l’alerte*
   - Cliquez sur l’icône **RSS** à côté de l’alerte → copiez l’URL.
4) Lancez le script :
```bash
FEEDS="https://example.com/votre_flux_rss" python main.py
```
Les fichiers `output/YYYY-MM-DD.md` et `output/latest.md` sont générés.

### Variables utiles
- `FEEDS` : une ou plusieurs URLs, séparées par virgule ou retour à la ligne
- `SENTENCES` : nb de phrases par résumé (défaut: 4)
- `MAX_PER_FEED` : nb max d’articles par flux (défaut: 20)
- `TIMEOUT` : timeout réseau (défaut: 20s)

## ☁️ Exécution automatique (GitHub Actions – gratuit)
Vous pouvez planifier l’exécution **tous les jours** depuis un dépôt GitHub :

1) Créez un nouveau dépôt et **uploadez** ces fichiers.
2) Activez **Actions** dans l’onglet GitHub *Actions* (la première exécution peut demander une confirmation).
3) Modifiez le fichier `.github/workflows/daily.yml` pour **ajouter votre URL RSS**.
4) Le workflow commitera le rapport dans `output/` chaque jour.

> **Note :** GitHub Actions utilise l’heure **UTC**. Ajustez l’horaire du `cron:` à votre convenance.

## 🔧 Personnalisation
- Plusieurs thématiques ? Ajoutez plusieurs URLs dans `FEEDS`.
- Vous voulez un export HTML ou e‑mail ? Ouvrez une issue/ticket : on peut l’ajouter facilement.
- Vous avez une clé API (OpenAI, Mistral…) et voulez un résumé **abstractive** plus “IA” ? On peut brancher ça en option.

## 🧠 Comment ça résume sans payer ?
On utilise un algorithme **extractif** (TextRank via `sumy`) qui sélectionne les phrases importantes — ça marche **hors‑ligne** pour le français.

## ❗️Limites connues
- Certains sites bloquent l’extraction automatique — le script marquera “Résumé indisponible”.
- Les liens Google Alerts sont des redirections : on tente d’extraire l’URL d’origine (`url=` / `q=`) pour de meilleurs résultats.

---

Fait pour être simple, gratuit, et extensible. 🙂
