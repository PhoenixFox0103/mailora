# OneByMail

OneByMail est une application locale et open source permettant d'envoyer un email distinct à chaque destinataire depuis un compte Gmail.

L'outil importe des contacts depuis Excel, CSV ou TXT, ou accepte une liste d'adresses collée directement dans l'interface. Chaque destinataire reçoit son propre message et ne voit aucune autre adresse dans le champ « À ».

> OneByMail est destiné aux communications légitimes, ciblées et responsables. L'utilisateur reste responsable du respect des limites de Gmail, de la confidentialité des données et des règles applicables aux communications électroniques.

## Fonctionnalités

- Import de contacts depuis `.xlsx`, `.xls`, `.csv` et `.txt`
- Ajout direct d'adresses email dans l'interface
- Détection et suppression des doublons
- Validation des adresses email
- Envoi d'un message distinct à chaque destinataire
- Personnalisation activable ou désactivable
- Variables dynamiques : `{{Prenom}}`, `{{Entreprise}}` et `{{Poste}}`
- Ajout d'une pièce jointe
- Envoi d'un email de test
- Délai configurable entre les emails
- Suivi des envois réussis et échoués
- Authentification sécurisée avec Google OAuth 2.0
- Exécution locale, sans serveur distant

## Technologies

- Python
- Flask
- HTML
- CSS
- JavaScript natif
- Pandas
- OpenPyXL
- Gmail API
- Google OAuth 2.0

## Architecture

```text
OneByMail/
├── data/
│   └── .gitkeep
├── templates/
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   └── index.html
├── uploads/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── app.py
├── credentials.example.json
├── gmail_service.py
├── README.md
└── requirements.txt
```

Les fichiers suivants sont créés ou ajoutés localement par chaque utilisateur et ne doivent jamais être publiés :

```text
.env
credentials.json
token.json
```

## Prérequis

- Python 3.10 ou version ultérieure
- pip
- Un compte Google avec Gmail activé
- Un projet Google Cloud personnel

## Installation

### 1. Télécharger le projet

Avec Git :

```bash
git clone https://github.com/VOTRE-UTILISATEUR/OneByMail.git
cd OneByMail
```

Ou depuis GitHub :

1. Cliquer sur **Code**
2. Cliquer sur **Download ZIP**
3. Extraire l'archive
4. Ouvrir le dossier dans Visual Studio Code

### 2. Créer l'environnement Python

Sous Windows :

```bash
py -m venv .venv
.venv\Scripts\activate
```

Sous macOS ou Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installer les dépendances

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration de Gmail API

OneByMail ne fournit aucun identifiant Google partagé. Chaque utilisateur doit créer son propre projet Google Cloud et son propre fichier `credentials.json`.

### 1. Créer un projet Google Cloud

1. Ouvrir la console Google Cloud : <https://console.cloud.google.com/>
2. Créer un nouveau projet
3. Donner un nom au projet, par exemple `OneByMail Local`

### 2. Activer Gmail API

Dans le projet Google Cloud :

```text
APIs & Services
→ Library
→ Gmail API
→ Enable
```

### 3. Configurer l'écran de consentement OAuth

Ouvrir :

```text
Google Auth Platform
→ Branding
```

Renseigner :

```text
App name : OneByMail Local
User support email : votre adresse Google
Developer contact information : votre adresse Google
```

Pour un compte Gmail personnel :

1. Choisir une audience **External**
2. Ouvrir **Audience**
3. Dans **Test users**, cliquer sur **Add users**
4. Ajouter l'adresse Gmail qui sera utilisée avec OneByMail

Si cette adresse n'est pas ajoutée pendant la phase de test, Google peut afficher l'erreur `403: access_denied`.

### 4. Créer le client OAuth

Ouvrir :

```text
Google Auth Platform
→ Clients
→ Create Client
```

Choisir :

```text
Application type : Desktop application
Name : OneByMail Desktop
```

Télécharger ensuite le fichier JSON.

### 5. Ajouter `credentials.json`

1. Renommer le fichier téléchargé en `credentials.json`
2. Le placer à la racine du projet, à côté de `app.py`

```text
OneByMail/
├── app.py
├── gmail_service.py
├── credentials.json
└── requirements.txt
```

Ne pas remplir manuellement le fichier à partir de `credentials.example.json`. Le fichier téléchargé depuis Google Cloud contient déjà les bonnes informations.

## Configuration de la clé Flask

La clé Flask protège la session locale utilisée par l'application. Elle ne vient pas de Google.

### 1. Générer une clé

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Créer `.env`

Copier `.env.example` et renommer la copie en `.env`.

Contenu attendu :

```env
FLASK_SECRET_KEY=COLLEZ_ICI_LA_CLE_GENEREE
```

Le fichier `.env` doit rester uniquement sur l'ordinateur de l'utilisateur.

## Premier lancement

```bash
python app.py
```

Ouvrir ensuite :

```text
http://127.0.0.1:5000
```

Lors du premier email de test :

1. Une fenêtre Google s'ouvre
2. Sélectionner le compte ajouté dans les utilisateurs de test
3. Autoriser OneByMail à envoyer des emails
4. L'application génère automatiquement `token.json`

`token.json` ne doit pas être créé ou modifié manuellement. Il contient l'autorisation OAuth locale et doit rester confidentiel.

## Format des contacts

Seule la colonne `Email` est obligatoire.

### Fichier simple

```csv
Email
contact1@entreprise.fr
contact2@entreprise.fr
```

### Fichier personnalisé

```csv
Email,Prenom,Entreprise,Poste
contact1@entreprise.fr,Marie,Entreprise A,Data Engineer
contact2@entreprise.fr,Thomas,Entreprise B,AI Engineer
```

### Fichier TXT

```text
contact1@entreprise.fr
contact2@entreprise.fr
contact3@entreprise.fr
```

Les adresses peuvent également être collées directement dans OneByMail et séparées par des lignes, des virgules, des points-virgules ou des espaces.

## Personnalisation

Lorsque la personnalisation est activée, les variables suivantes sont disponibles :

```text
{{Prenom}}
{{Entreprise}}
{{Poste}}
```

Exemple :

```text
Bonjour {{Prenom}},

Je vous contacte concernant les opportunités de {{Poste}} au sein de {{Entreprise}}.
```

Chaque variable est remplacée par la valeur correspondant au destinataire.

Lorsque la personnalisation est désactivée, utilisez un message général ne dépendant pas de ces variables.

## Confidentialité

OneByMail fonctionne localement :

- les contacts restent sur l'ordinateur de l'utilisateur ;
- les pièces jointes sont stockées temporairement puis supprimées ;
- le mot de passe Gmail n'est jamais demandé ni enregistré ;
- Google OAuth 2.0 gère l'autorisation ;
- chaque utilisateur utilise son propre projet Google Cloud ;
- chaque destinataire reçoit un email indépendant.

## Fichiers confidentiels

Le fichier `.gitignore` doit contenir au minimum :

```gitignore
.venv/
venv/
__pycache__/
*.pyc

credentials.json
token.json
.env

data/*
!data/.gitkeep

uploads/*
!uploads/.gitkeep

*.xlsx
*.xls

.vscode/
.DS_Store
Thumbs.db
```

Avant chaque publication :

```bash
git status
```

Vérifier que `credentials.json`, `token.json` et `.env` ne sont pas suivis par Git.

## Dépannage

### Erreur `403: access_denied`

Vérifier que :

- l'audience OAuth est configurée ;
- le compte Gmail est ajouté dans **Test users** ;
- le fichier `credentials.json` appartient au même projet Google Cloud ;
- le client OAuth est de type **Desktop application**.

Supprimer ensuite l'ancien `token.json`, puis recommencer l'autorisation.

### Le CSS ne s'affiche pas

Vérifier dans `app.py` :

```python
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="templates/static",
    static_url_path="/static",
)
```

Puis ouvrir :

```text
http://127.0.0.1:5000/static/style.css
```

### Les variables apparaissent vides

Dans le modèle HTML Flask, les variables de publipostage doivent être protégées avec `{% raw %}` et `{% endraw %}` afin que Jinja ne les supprime pas avant le chargement de la page.

## Utilisation responsable

OneByMail ne contourne pas les quotas, les limites d'envoi ou les filtres antispam de Gmail.

Utilisez l'outil uniquement pour :

- des destinataires pertinents ;
- des communications légitimes ;
- des listes autorisées ;
- des messages respectant les règles applicables.

Commencez par un test sur une ou deux adresses que vous contrôlez avant d'envoyer une campagne plus importante.

## Contribution

Les contributions sont les bienvenues :

1. Créer un fork
2. Créer une branche
3. Effectuer les modifications
4. Ouvrir une Pull Request

## Licence

Ajoutez la licence de votre choix au dépôt, par exemple la licence MIT, si vous souhaitez autoriser la réutilisation et la modification du projet.
