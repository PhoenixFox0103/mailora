import atexit
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

import pandas as pd

from apscheduler.schedulers.background import (
    BackgroundScheduler,
)
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from gmail_service import get_gmail_service, send_email


BASE_DIR = Path(__file__).resolve().parent

DATA_FOLDER = BASE_DIR / "data"
UPLOAD_FOLDER = BASE_DIR / "uploads"

CONTACTS_FILE = DATA_FOLDER / "contacts.json"
CAMPAIGN_FILE = DATA_FOLDER / "campaign_status.json"

DATA_FOLDER.mkdir(exist_ok=True)
UPLOAD_FOLDER.mkdir(exist_ok=True)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="templates/static",
    static_url_path="/static",
)

app.secret_key = "change-this-local-secret-key"
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024


scheduler = BackgroundScheduler(
    timezone=ZoneInfo("UTC"),
)

scheduler.start()


atexit.register(
    lambda: scheduler.shutdown(
        wait=False
    )
)


AVAILABLE_TIMEZONES = [
    {
        "value": "Africa/Tunis",
        "label": "Tunis",
    },
    {
        "value": "Africa/Algiers",
        "label": "Alger",
    },
    {
        "value": "Africa/Casablanca",
        "label": "Casablanca",
    },
    {
        "value": "Africa/Cairo",
        "label": "Le Caire",
    },
    {
        "value": "Europe/Paris",
        "label": "Paris",
    },
    {
        "value": "Europe/London",
        "label": "Londres",
    },
    {
        "value": "Europe/Brussels",
        "label": "Bruxelles",
    },
    {
        "value": "Europe/Berlin",
        "label": "Berlin",
    },
    {
        "value": "Europe/Madrid",
        "label": "Madrid",
    },
    {
        "value": "Europe/Rome",
        "label": "Rome",
    },
    {
        "value": "America/New_York",
        "label": "New York",
    },
    {
        "value": "America/Toronto",
        "label": "Toronto",
    },
    {
        "value": "America/Chicago",
        "label": "Chicago",
    },
    {
        "value": "America/Denver",
        "label": "Denver",
    },
    {
        "value": "America/Los_Angeles",
        "label": "Los Angeles",
    },
    {
        "value": "America/Sao_Paulo",
        "label": "São Paulo",
    },
    {
        "value": "Asia/Dubai",
        "label": "Dubaï",
    },
    {
        "value": "Asia/Riyadh",
        "label": "Riyad",
    },
    {
        "value": "Asia/Kolkata",
        "label": "Inde",
    },
    {
        "value": "Asia/Singapore",
        "label": "Singapour",
    },
    {
        "value": "Asia/Tokyo",
        "label": "Tokyo",
    },
    {
        "value": "Australia/Sydney",
        "label": "Sydney",
    },
    {
        "value": "Pacific/Auckland",
        "label": "Auckland",
    },
    {
        "value": "UTC",
        "label": "UTC",
    },
]


ALLOWED_CONTACT_EXTENSIONS = {
    "csv",
    "xlsx",
    "xls",
    "txt",
}

ALLOWED_ATTACHMENT_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "png",
    "jpg",
    "jpeg",
}

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

campaign_lock = threading.RLock()
stop_event = threading.Event()


campaign_state = {
    "status": "idle",
    "total": 0,
    "processed": 0,
    "sent": 0,
    "failed": 0,
    "current_email": "",
    "results": [],
    "started_at": None,
    "finished_at": None,
    "scheduled_at": None,
    "scheduled_timezone": None,
    "scheduled_display": None,
    "job_id": None,
}

def create_empty_campaign_state():
    """
    Retourne un nouvel état de campagne vide.
    """

    return {
        "status": "idle",
        "total": 0,
        "processed": 0,
        "sent": 0,
        "failed": 0,
        "current_email": "",
        "results": [],
        "started_at": None,
        "finished_at": None,
        "scheduled_at": None,
        "scheduled_timezone": None,
        "scheduled_display": None,
        "job_id": None,
    }

def reset_application_data():
    """
    Remet les données temporaires de l'application à zéro.

    Supprime :
    - les contacts importés ;
    - les anciens résultats ;
    - la progression ;
    - les compteurs d'envoi.

    Ne supprime pas :
    - credentials.json ;
    - token.json ;
    - la connexion Google.
    """

    global campaign_state

    # Supprime la liste des contacts enregistrée localement.
    CONTACTS_FILE.unlink(
        missing_ok=True
    )

    # Supprime l'ancien statut de campagne.
    CAMPAIGN_FILE.unlink(
        missing_ok=True
    )

    # Remet l'état de la campagne à zéro.
    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
        )
def reset_campaign_state():
    """
    Réinitialise l'affichage de la campagne.

    Cette fonction ne supprime pas :
    - le token Google ;
    - les identifiants OAuth ;
    - les paramètres Gmail.
    """

    global campaign_state

    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
    )

    CAMPAIGN_FILE.unlink(
        missing_ok=True
    )

def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in allowed_extensions
    )


def is_valid_email(value):
    if value is None:
        return False

    email = str(value).strip().lower()

    return bool(
        EMAIL_PATTERN.fullmatch(email)
    )


def normalize_column_name(column):
    normalized = str(column).strip().lower()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ô": "o",
        "ö": "o",
        "î": "i",
        "ï": "i",
        "ç": "c",
        "_": " ",
        "-": " ",
    }

    for old_value, new_value in replacements.items():
        normalized = normalized.replace(
            old_value,
            new_value,
        )

    return " ".join(
        normalized.split()
    )


def create_email_only_contacts(values):
    """
    Transforme une liste de valeurs en contacts.

    Les doublons et les adresses invalides sont supprimés.
    """

    contacts = []
    existing_emails = set()

    for value in values:
        if value is None:
            continue

        email = str(value).strip().lower()

        # Retire quelques caractères fréquents autour des emails.
        email = email.strip(
            " \t\r\n\"'<>(),"
        )
        

        if not is_valid_email(email):
            continue

        if email in existing_emails:
            continue

        existing_emails.add(email)

        contacts.append({
            "Email": email,
            "Prenom": "",
            "Entreprise": "",
            "Poste": "",
        })

    return contacts


def extract_emails_from_text(text):
    """
    Extrait les adresses depuis :
    - plusieurs lignes ;
    - des virgules ;
    - des points-virgules ;
    - des espaces ou tabulations.
    """

    if not text:
        return []

    possible_emails = re.split(
        r"[\s,;]+",
        text,
    )

    return create_email_only_contacts(
        possible_emails
    )


def find_column_mapping(dataframe):
    column_mapping = {}

    for column in dataframe.columns:
        normalized = normalize_column_name(
            column
        )

        if normalized in {
            "email",
            "mail",
            "e mail",
            "adresse email",
            "adresse mail",
            "email address",
        }:
            column_mapping[column] = "Email"

        elif normalized in {
            "prenom",
            "first name",
            "firstname",
        }:
            column_mapping[column] = "Prenom"

        elif normalized in {
            "entreprise",
            "societe",
            "company",
            "organization",
            "organisation",
        }:
            column_mapping[column] = "Entreprise"

        elif normalized in {
            "poste",
            "position",
            "job",
            "role",
            "job title",
        }:
            column_mapping[column] = "Poste"

    return column_mapping


def prepare_structured_contacts(dataframe):
    """
    Lit les contacts d'un fichier ayant une colonne Email identifiée.
    """

    column_mapping = find_column_mapping(
        dataframe
    )

    dataframe = dataframe.rename(
        columns=column_mapping
    )

    if "Email" not in dataframe.columns:
        return None

    for optional_column in [
        "Prenom",
        "Entreprise",
        "Poste",
    ]:
        if optional_column not in dataframe.columns:
            dataframe[optional_column] = ""

    dataframe = dataframe[
        [
            "Email",
            "Prenom",
            "Entreprise",
            "Poste",
        ]
    ].copy()

    dataframe = dataframe.fillna("")

    for column in dataframe.columns:
        dataframe[column] = (
            dataframe[column]
            .astype(str)
            .str.strip()
        )

    dataframe["Email"] = (
        dataframe["Email"]
        .str.lower()
    )

    dataframe = dataframe[
        dataframe["Email"].apply(
            is_valid_email
        )
    ]

    dataframe = dataframe.drop_duplicates(
        subset=["Email"],
        keep="first",
    )

    return dataframe.to_dict(
        orient="records"
    )


def extract_emails_from_dataframe(dataframe):
    """
    Recherche des emails dans toutes les cellules du fichier.

    Cela permet de lire un fichier avec une seule colonne,
    même si la colonne n'a pas de titre.
    """

    all_values = []

    # Dans un fichier sans en-tête, pandas peut avoir considéré
    # la première adresse comme le nom de la colonne.
    all_values.extend(
        list(dataframe.columns)
    )

    for column in dataframe.columns:
        all_values.extend(
            dataframe[column]
            .dropna()
            .astype(str)
            .tolist()
        )

    extracted_values = []

    for value in all_values:
        parts = re.split(
            r"[\s,;]+",
            str(value),
        )

        extracted_values.extend(parts)

    return create_email_only_contacts(
        extracted_values
    )


def read_csv_file(file_path):
    """
    Lit un CSV structuré ou un CSV contenant seulement des emails.
    """

    encodings = [
        "utf-8-sig",
        "utf-8",
        "latin-1",
    ]

    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(
                file_path,
                sep=None,
                engine="python",
                encoding=encoding,
            )
        except UnicodeDecodeError as error:
            last_error = error
        except pd.errors.EmptyDataError as error:
            raise ValueError(
                "Le fichier CSV est vide."
            ) from error

    raise ValueError(
        f"Lecture du CSV impossible : {last_error}"
    )


def read_contacts(file_path):
    """
    Lit les contacts depuis XLSX, XLS, CSV ou TXT.

    Seule l'adresse email est obligatoire.
    """

    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        try:
            text = file_path.read_text(
                encoding="utf-8-sig"
            )
        except UnicodeDecodeError:
            text = file_path.read_text(
                encoding="latin-1"
            )

        contacts = extract_emails_from_text(
            text
        )

        if not contacts:
            raise ValueError(
                "Aucune adresse email valide trouvée "
                "dans le fichier TXT."
            )

        return contacts

    if suffix == ".csv":
        dataframe = read_csv_file(
            file_path
        )

    elif suffix == ".xlsx":
        dataframe = pd.read_excel(
            file_path,
            engine="openpyxl",
        )

    elif suffix == ".xls":
        dataframe = pd.read_excel(
            file_path,
            engine="xlrd",
        )

    else:
        raise ValueError(
            "Formats acceptés : XLSX, XLS, CSV et TXT."
        )

    structured_contacts = prepare_structured_contacts(
        dataframe
    )

    if structured_contacts:
        return structured_contacts

    contacts = extract_emails_from_dataframe(
        dataframe
    )

    if not contacts:
        raise ValueError(
            "Aucune adresse email valide n'a été trouvée."
        )

    return contacts


def merge_contacts(existing_contacts, new_contacts):
    """
    Fusionne deux listes en supprimant les doublons.

    Si un contact déjà existant possède des champs vides,
    les nouvelles données peuvent les compléter.
    """

    contacts_by_email = {}

    for contact in existing_contacts + new_contacts:
        email = contact.get(
            "Email",
            "",
        ).strip().lower()

        if not is_valid_email(email):
            continue

        if email not in contacts_by_email:
            contacts_by_email[email] = {
                "Email": email,
                "Prenom": contact.get("Prenom", ""),
                "Entreprise": contact.get("Entreprise", ""),
                "Poste": contact.get("Poste", ""),
            }
        else:
            existing = contacts_by_email[email]

            for field in [
                "Prenom",
                "Entreprise",
                "Poste",
            ]:
                if (
                    not existing.get(field)
                    and contact.get(field)
                ):
                    existing[field] = contact[field]

    return list(
        contacts_by_email.values()
    )


def save_contacts(contacts):
    CONTACTS_FILE.write_text(
        json.dumps(
            contacts,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_contacts():
    if not CONTACTS_FILE.exists():
        return []

    try:
        contacts = json.loads(
            CONTACTS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(contacts, list):
            return []

        return contacts

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return []


def save_campaign_state():
    with campaign_lock:
        state_copy = {
            **campaign_state,
            "results": list(
                campaign_state["results"]
            ),
        }

    CAMPAIGN_FILE.write_text(
        json.dumps(
            state_copy,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def replace_variables(text, contact):
    replacements = {
        "{{Prenom}}": contact.get(
            "Prenom",
            "",
        ),
        "{{Entreprise}}": contact.get(
            "Entreprise",
            "",
        ),
        "{{Poste}}": contact.get(
            "Poste",
            "",
        ),
    }

    result = text

    for variable, value in replacements.items():
        result = result.replace(
            variable,
            str(value),
        )

    return result


def clean_identical_message(text):
    """
    Supprime les variables lorsque la personnalisation
    est désactivée.
    """

    result = re.sub(
        r"{{\s*[^}]+\s*}}",
        "",
        text,
    )

    # Nettoie les espaces inutiles avant les retours à la ligne.
    result = re.sub(
        r"[ \t]+\n",
        "\n",
        result,
    )

    # Limite les groupes excessifs de lignes vides.
    result = re.sub(
        r"\n{4,}",
        "\n\n\n",
        result,
    )

    return result.strip()


def personalize_text(
    text,
    contact,
    personalization_enabled,
):
    if personalization_enabled:
        return replace_variables(
            text,
            contact,
        ).strip()

    return clean_identical_message(
        text
    )


def create_temporary_attachment(attachment):
    """
    Enregistre temporairement la pièce jointe.

    Retourne :
    - le chemin temporaire ;
    - le nom original sécurisé du fichier.
    """

    if not attachment or not attachment.filename:
        return None, None

    if not allowed_file(
        attachment.filename,
        ALLOWED_ATTACHMENT_EXTENSIONS,
    ):
        raise ValueError(
            "Format de pièce jointe non accepté. "
            "Formats autorisés : PDF, DOC, DOCX, "
            "PNG, JPG et JPEG."
        )

    original_filename = secure_filename(
        attachment.filename
    )

    if not original_filename:
        original_filename = "piece_jointe"

    temporary_filename = (
        f"{uuid.uuid4().hex}_"
        f"{original_filename}"
    )

    attachment_path = (
        UPLOAD_FOLDER
        / temporary_filename
    )

    attachment.save(
        attachment_path
    )

    return attachment_path, original_filename


def run_campaign(
    contacts,
    subject,
    body,
    personalization_enabled,
    delay_seconds,
    attachment_path,
    attachment_name,
):
    """
    Exécute les envois dans un thread local en arrière-plan.
    """

    global campaign_state

    try:
        gmail_service = get_gmail_service()

    except Exception as error:
        with campaign_lock:
            campaign_state["status"] = "error"
            campaign_state["results"].append({
                "email": "",
                "status": "failed",
                "message": (
                    "Connexion Gmail impossible : "
                    f"{error}"
                ),
            })
            campaign_state["failed"] += 1
            campaign_state["finished_at"] = (
                datetime.now().isoformat()
            )

        save_campaign_state()

        if attachment_path:
            Path(attachment_path).unlink(
                missing_ok=True
            )

        return

    try:
        for index, contact in enumerate(contacts):
            if stop_event.is_set():
                with campaign_lock:
                    campaign_state["status"] = "stopped"
                    campaign_state["current_email"] = ""
                    campaign_state["finished_at"] = (
                        datetime.now().isoformat()
                    )

                save_campaign_state()
                return

            recipient = contact.get(
                "Email",
                "",
            ).strip().lower()

            with campaign_lock:
                campaign_state["current_email"] = recipient

            final_subject = personalize_text(
                subject,
                contact,
                personalization_enabled,
            )

            final_body = personalize_text(
                body,
                contact,
                personalization_enabled,
            )

            try:
                response = send_email(
                    service=gmail_service,
                    recipient=recipient,
                    subject=final_subject,
                    body=final_body,
                    attachment_path=attachment_path,
                    attachment_name=attachment_name,
                )

                result = {
                    "email": recipient,
                    "status": "sent",
                    "message": "Email envoyé",
                    "message_id": response.get("id"),
                }

                with campaign_lock:
                    campaign_state["sent"] += 1

            except Exception as error:
                result = {
                    "email": recipient,
                    "status": "failed",
                    "message": str(error),
                }

                with campaign_lock:
                    campaign_state["failed"] += 1

            with campaign_lock:
                campaign_state["processed"] += 1
                campaign_state["results"].append(
                    result
                )

            save_campaign_state()

            is_last_contact = (
                index == len(contacts) - 1
            )

            if not is_last_contact:
                # stop_event.wait permet d'interrompre la pause.
                stop_event.wait(
                    delay_seconds
                )

        with campaign_lock:
            campaign_state["status"] = "completed"
            campaign_state["current_email"] = ""
            campaign_state["finished_at"] = (
                datetime.now().isoformat()
            )

        save_campaign_state()
        CONTACTS_FILE.unlink(
            missing_ok=True
        )

    finally:
        if attachment_path:
            try:
                Path(attachment_path).unlink(
                    missing_ok=True
                )
            except OSError:
                pass

def run_scheduled_campaign(
    contacts,
    subject,
    body,
    personalization_enabled,
    delay_seconds,
    attachment_path,
    attachment_name,
):
    """
    Lance automatiquement une campagne programmée.
    """

    global campaign_state

    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
        )

        campaign_state.update({
            "status": "running",
            "total": len(contacts),
            "started_at": (
                datetime.now(
                    ZoneInfo("UTC")
                ).isoformat()
            ),
        })

    stop_event.clear()
    save_campaign_state()

    run_campaign(
        contacts=contacts,
        subject=subject,
        body=body,
        personalization_enabled=(
            personalization_enabled
        ),
        delay_seconds=delay_seconds,
        attachment_path=attachment_path,
        attachment_name=attachment_name,
    )
    
@app.route("/")
def index():
    """
    Affiche l'application.

    Après un import, preserve_contacts_once permet d'afficher
    la liste pendant la redirection automatique.

    Lors du prochain F5, Ctrl+R ou clic sur Actualiser,
    l'application est remise à zéro.
    """

    with campaign_lock:
        protected_campaign = (
            campaign_state["status"]
            in {
                "running",
                "scheduled",
            }
        )


    # Cet indicateur existe uniquement pendant la redirection
    # automatique qui suit l'import.
    preserve_contacts_once = session.pop(
        "preserve_contacts_once",
        False,
    )

    # Un rafraîchissement manuel réinitialise l'application.
    # Une campagne en cours reste toutefois protégée.
    if (
        not protected_campaign
        and not preserve_contacts_once
):
        reset_application_data()

    contacts = load_contacts()

    return render_template(
        "index.html",
        contacts=contacts[:10],
        contact_count=len(contacts),
        available_timezones=AVAILABLE_TIMEZONES,
        default_timezone="Africa/Tunis",
)


@app.route(
    "/upload-contacts",
    methods=["POST"],
)
def upload_contacts():
    contacts_file = request.files.get(
        "contacts_file"
    )

    if (
        not contacts_file
        or not contacts_file.filename
    ):
        flash(
            "Sélectionnez un fichier Excel, CSV ou TXT.",
            "error",
        )

        return redirect(
            url_for("index")
        )

    if not allowed_file(
        contacts_file.filename,
        ALLOWED_CONTACT_EXTENSIONS,
    ):
        flash(
            "Formats acceptés : XLSX, XLS, CSV et TXT.",
            "error",
        )

        return redirect(
            url_for("index")
        )

    temporary_name = (
        f"{uuid.uuid4().hex}_"
        f"{secure_filename(contacts_file.filename)}"
    )

    temporary_path = (
        DATA_FOLDER
        / temporary_name
    )

    contacts_file.save(
        temporary_path
    )

    try:
        imported_contacts = read_contacts(
            temporary_path
        )

        existing_contacts = load_contacts()

        final_contacts = merge_contacts(
            existing_contacts,
            imported_contacts,
        )

        old_emails = {
            contact.get("Email", "").lower()
            for contact in existing_contacts
        }

        added_count = sum(
            contact["Email"].lower() not in old_emails
            for contact in imported_contacts
        )

        ignored_count = (
            len(imported_contacts) - added_count
        )

        save_contacts(
            final_contacts
        )
        
        # Conserve la liste pendant la redirection automatique
# qui suit immédiatement l'import.
        session["preserve_contacts_once"] = True

        if ignored_count:
            message = (
                f"{added_count} nouvelle(s) adresse(s) ajoutée(s). "
                f"{ignored_count} doublon(s) ignoré(s). "
                f"Total : {len(final_contacts)} contact(s)."
            )
        else:
            message = (
                f"{added_count} nouvelle(s) adresse(s) ajoutée(s). "
                f"Total : {len(final_contacts)} contact(s)."
            )

        flash(
            message,
            "success",
        )

    except Exception as error:
        flash(
            f"Import impossible : {error}",
            "error",
        )

    finally:
        temporary_path.unlink(
            missing_ok=True
        )

    return redirect(
        url_for("index")
    )


@app.route(
    "/add-direct-emails",
    methods=["POST"],
)
def add_direct_emails():
    direct_emails = request.form.get(
        "direct_emails",
        "",
    ).strip()

    if not direct_emails:
        flash(
            "Collez au moins une adresse email.",
            "error",
        )

        return redirect(
            url_for("index")
        )

    new_contacts = extract_emails_from_text(
        direct_emails
    )

    if not new_contacts:
        flash(
            "Aucune adresse email valide n'a été détectée.",
            "error",
        )

        return redirect(
            url_for("index")
        )

    existing_contacts = load_contacts()

    old_emails = {
        contact.get("Email", "").lower()
        for contact in existing_contacts
    }

    added_count = sum(
        contact["Email"].lower() not in old_emails
        for contact in new_contacts
    )

    ignored_count = (
        len(new_contacts) - added_count
    )

    final_contacts = merge_contacts(
        existing_contacts,
        new_contacts,
    )

    save_contacts(
        final_contacts
    )
    session["preserve_contacts_once"] = True

    if ignored_count:
        message = (
            f"{added_count} nouvelle(s) adresse(s) ajoutée(s). "
            f"{ignored_count} doublon(s) ignoré(s). "
            f"Total : {len(final_contacts)} contact(s)."
        )
    else:
        message = (
            f"{added_count} nouvelle(s) adresse(s) ajoutée(s). "
            f"Total : {len(final_contacts)} contact(s)."
        )

    flash(
        message,
        "success",
    )

    return redirect(
        url_for("index")
    )


@app.route(
    "/clear-contacts",
    methods=["POST"],
)
def clear_contacts():
    """
    Supprime manuellement les contacts et les résultats.
    """

    with campaign_lock:
        campaign_running = (
            campaign_state["status"]
            in {
                "running",
                "scheduled",
            }
)

    if campaign_running:
        flash(
            "Arrêtez ou annulez la campagne avant de supprimer les contacts."
            "error",
        )

        # La liste doit rester visible après cette redirection.
        session["preserve_contacts_once"] = True

        return redirect(
            url_for("index")
        )

    reset_application_data()

    # Supprime un éventuel ancien indicateur.
    session.pop(
        "preserve_contacts_once",
        None,
    )

    flash(
        "La liste de contacts et les résultats ont été supprimés.",
        "success",
    )

    # Conserve uniquement le message après la redirection.
    session["preserve_contacts_once"] = True

    return redirect(
        url_for("index")
    )


@app.route(
    "/send-test",
    methods=["POST"],
)
def send_test():
    test_email = request.form.get(
        "test_email",
        "",
    ).strip().lower()

    subject = request.form.get(
        "subject",
        "",
    ).strip()

    body = request.form.get(
        "body",
        "",
    ).strip()

    personalization_enabled = (
        request.form.get("personalization")
        == "on"
    )

    if not is_valid_email(test_email):
        return jsonify({
            "success": False,
            "message": (
                "L'adresse email de test est invalide."
            ),
        }), 400

    if not subject or not body:
        return jsonify({
            "success": False,
            "message": (
                "L'objet et le message sont obligatoires."
            ),
        }), 400

    test_contact = {
        "Email": test_email,
        "Prenom": "Cyrine",
        "Entreprise": "Entreprise Test",
        "Poste": "Data Engineer",
    }

    attachment_path = None
    attachment_name = None
    
    try:
        attachment_path, attachment_name = (
            create_temporary_attachment(
        request.files.get("attachment")
    )
)

        service = get_gmail_service()

        send_email(
            service=service,
            recipient=test_email,
            subject=personalize_text(
                subject,
                test_contact,
                personalization_enabled,
            ),
            body=personalize_text(
                body,
                test_contact,
                personalization_enabled,
            ),
            attachment_path=attachment_path,
            attachment_name=attachment_name,
        )

        return jsonify({
            "success": True,
            "message": (
                f"Email de test envoyé à {test_email}."
            ),
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 500

    finally:
        if attachment_path:
            Path(attachment_path).unlink(
                missing_ok=True
            )


@app.route(
    "/start-campaign",
    methods=["POST"],
)
def start_campaign():
    global campaign_state

    with campaign_lock:
        if campaign_state["status"] in {
            "running",
            "scheduled",
        }:
            return jsonify({
                "success": False,
                "message": (
                    "Une campagne est déjà en cours "
                    "ou programmée."
                ),
            }), 409

    contacts = load_contacts()

    if not contacts:
        return jsonify({
            "success": False,
            "message": (
                "Importez ou saisissez d'abord des adresses email."
            ),
        }), 400

    subject = request.form.get(
        "subject",
        "",
    ).strip()

    body = request.form.get(
        "body",
        "",
    ).strip()

    personalization_enabled = (
        request.form.get("personalization")
        == "on"
    )

    authorized_use = (
        request.form.get("authorized_use")
        == "on"
    )

    if not authorized_use:
        return jsonify({
            "success": False,
            "message": (
                "Confirmez l'utilisation responsable de la liste."
            ),
        }), 400

    if not subject or not body:
        return jsonify({
            "success": False,
            "message": (
                "L'objet et le message sont obligatoires."
            ),
        }), 400

    try:
        delay_seconds = int(
            request.form.get(
                "delay",
                "30",
            )
        )
    except ValueError:
        delay_seconds = 30

    delay_seconds = max(
        5,
        min(delay_seconds, 3600),
    )

    attachment_path = None
    attachment_name = None
    try:
        
        attachment_path, attachment_name = (
            create_temporary_attachment(
                request.files.get("attachment")
            )
        )
    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 400

    stop_event.clear()

    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
        )

        campaign_state.update({
            "status": "running",
            "total": len(contacts),
            "started_at": (
                datetime.now(
                    ZoneInfo("UTC")
                ).isoformat()
            ),
        })

    save_campaign_state()

    campaign_thread = threading.Thread(
        target=run_campaign,
        args=(
            contacts,
            subject,
            body,
            personalization_enabled,
            delay_seconds,
            attachment_path,
            attachment_name,
        ),
        daemon=True,
    )

    campaign_thread.start()

    return jsonify({
        "success": True,
        "message": (
            f"Campagne lancée pour {len(contacts)} contact(s)."
        ),
    })


@app.route(
    "/schedule-campaign",
    methods=["POST"],
)
def schedule_campaign():
    """
    Programme une campagne à une date,
    une heure et dans un fuseau choisis.
    """

    global campaign_state

    with campaign_lock:
        if campaign_state["status"] in {
            "running",
            "scheduled",
        }:
            return jsonify({
                "success": False,
                "message": (
                    "Une campagne est déjà en cours "
                    "ou programmée."
                ),
            }), 409

    contacts = load_contacts()

    if not contacts:
        return jsonify({
            "success": False,
            "message": (
                "Importez ou saisissez d'abord "
                "des adresses email."
            ),
        }), 400

    subject = request.form.get(
        "subject",
        "",
    ).strip()

    body = request.form.get(
        "body",
        "",
    ).strip()

    scheduled_at_value = request.form.get(
        "scheduled_at",
        "",
    ).strip()

    timezone_name = request.form.get(
        "scheduled_timezone",
        "Africa/Tunis",
    ).strip()

    personalization_enabled = (
        request.form.get("personalization")
        == "on"
    )

    authorized_use = (
        request.form.get("authorized_use")
        == "on"
    )

    if not authorized_use:
        return jsonify({
            "success": False,
            "message": (
                "Confirmez l'utilisation responsable "
                "de la liste."
            ),
        }), 400

    if not subject or not body:
        return jsonify({
            "success": False,
            "message": (
                "L'objet et le message sont obligatoires."
            ),
        }), 400

    if not scheduled_at_value:
        return jsonify({
            "success": False,
            "message": (
                "Choisissez une date et une heure."
            ),
        }), 400

    allowed_timezone_names = {
        timezone["value"]
        for timezone in AVAILABLE_TIMEZONES
    }

    if timezone_name not in allowed_timezone_names:
        return jsonify({
            "success": False,
            "message": (
                "Le fuseau horaire sélectionné "
                "n'est pas autorisé."
            ),
        }), 400

    try:
        selected_timezone = ZoneInfo(
            timezone_name
        )

    except ZoneInfoNotFoundError:
        return jsonify({
            "success": False,
            "message": (
                "Fuseau horaire introuvable. "
                "Vérifiez que tzdata est installé."
            ),
        }), 400

    try:
        naive_datetime = datetime.fromisoformat(
            scheduled_at_value
        )

        scheduled_datetime = naive_datetime.replace(
            tzinfo=selected_timezone
        )

    except ValueError:
        return jsonify({
            "success": False,
            "message": (
                "La date sélectionnée est invalide."
            ),
        }), 400

    if scheduled_datetime <= datetime.now(
        selected_timezone
    ):
        return jsonify({
            "success": False,
            "message": (
                "Choisissez une date et "
                "une heure futures."
            ),
        }), 400

    try:
        delay_seconds = int(
            request.form.get(
                "delay",
                "30",
            )
        )
    except ValueError:
        delay_seconds = 30

    delay_seconds = max(
        5,
        min(delay_seconds, 3600),
    )

    attachment_path = None
    attachment_name = None

    try:
        attachment_path, attachment_name = (
            create_temporary_attachment(
                request.files.get(
                    "attachment"
                )
            )
        )

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 400

    job_id = (
        f"campaign_{uuid.uuid4().hex}"
    )

    try:
        scheduler.add_job(
            func=run_scheduled_campaign,
            trigger="date",
            run_date=scheduled_datetime,
            id=job_id,
            args=[
                contacts,
                subject,
                body,
                personalization_enabled,
                delay_seconds,
                attachment_path,
                attachment_name,
            ],
            misfire_grace_time=300,
        )

    except Exception as error:
        if attachment_path:
            Path(attachment_path).unlink(
                missing_ok=True
            )

        return jsonify({
            "success": False,
            "message": (
                "Impossible de programmer "
                f"la campagne : {error}"
            ),
        }), 500

    timezone_label = next(
        (
            timezone["label"]
            for timezone in AVAILABLE_TIMEZONES
            if timezone["value"]
            == timezone_name
        ),
        timezone_name,
    )

    scheduled_display = (
        scheduled_datetime.strftime(
            "%d/%m/%Y à %H:%M"
        )
        + f" · {timezone_label}"
        + f" ({timezone_name})"
    )

    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
        )

        campaign_state.update({
            "status": "scheduled",
            "total": len(contacts),
            "scheduled_at": (
                scheduled_datetime.isoformat()
            ),
            "scheduled_timezone": (
                timezone_name
            ),
            "scheduled_display": (
                scheduled_display
            ),
            "job_id": job_id,
        })

    save_campaign_state()

    return jsonify({
        "success": True,
        "message": (
            "Campagne programmée pour le "
            f"{scheduled_display}."
        ),
        "scheduled_at": (
            scheduled_datetime.isoformat()
        ),
        "scheduled_timezone": timezone_name,
        "scheduled_display": scheduled_display,
    })
    
@app.route(
    "/cancel-scheduled-campaign",
    methods=["POST"],
)
def cancel_scheduled_campaign():
    """
    Annule une campagne programmée.
    """

    global campaign_state

    with campaign_lock:
        status = campaign_state["status"]
        job_id = campaign_state.get(
            "job_id"
        )

    if status != "scheduled" or not job_id:
        return jsonify({
            "success": False,
            "message": (
                "Aucune campagne programmée."
            ),
        }), 400

    job = scheduler.get_job(
        job_id
    )

    attachment_path = None

    if job and job.args:
        attachment_path = job.args[5]

    try:
        scheduler.remove_job(
            job_id
        )
    except Exception:
        pass

    if attachment_path:
        Path(attachment_path).unlink(
            missing_ok=True
        )

    with campaign_lock:
        campaign_state = (
            create_empty_campaign_state()
        )

    save_campaign_state()

    return jsonify({
        "success": True,
        "message": (
            "La programmation a été annulée."
        ),
    })
    
    
@app.route("/campaign-status")
def get_campaign_status():
    with campaign_lock:
        state_copy = {
            **campaign_state,
            "results": list(
                campaign_state["results"][-100:]
            ),
        }

    return jsonify(
        state_copy
    )


@app.route(
    "/stop-campaign",
    methods=["POST"],
)
def stop_campaign():
    with campaign_lock:
        is_running = (
            campaign_state["status"] == "running"
        )

    if not is_running:
        return jsonify({
            "success": False,
            "message": (
                "Aucune campagne n'est en cours."
            ),
        }), 400

    stop_event.set()

    return jsonify({
        "success": True,
        "message": (
            "Demande d'arrêt envoyée."
        ),
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False,
        threaded=True,
    )
