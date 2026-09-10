import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    """
    Connecte l'utilisateur à Gmail avec OAuth 2.0.

    Au premier lancement, une fenêtre Google est ouverte.
    Après l'autorisation, un fichier token.json est créé localement.
    """

    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE),
            SCOPES,
        )

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "Le fichier credentials.json est introuvable. "
                "Créez des identifiants OAuth Google de type "
                "'Application de bureau', téléchargez le fichier JSON "
                "et placez-le à la racine du projet."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES,
        )

        credentials = flow.run_local_server(
            port=0,
            prompt="consent",
        )

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def create_email(
    recipient,
    subject,
    body,
    attachment_path=None,
    attachment_name=None,
):
    """
    Crée un email avec un seul destinataire.

    attachment_path :
        emplacement temporaire du fichier sur l'ordinateur.

    attachment_name :
        nom original affiché dans l'email reçu.
    """

    message = EmailMessage()

    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path:
        attachment_path = Path(attachment_path)

        if attachment_path.exists():
            visible_filename = (
                attachment_name
                if attachment_name
                else attachment_path.name
            )

            mime_type, _ = mimetypes.guess_type(
                visible_filename
            )

            if mime_type:
                main_type, sub_type = mime_type.split(
                    "/",
                    1,
                )
            else:
                main_type = "application"
                sub_type = "octet-stream"

            with attachment_path.open("rb") as attachment_file:
                message.add_attachment(
                    attachment_file.read(),
                    maintype=main_type,
                    subtype=sub_type,
                    filename=visible_filename,
                )

    raw_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    return {
        "raw": raw_message,
    }


def send_email(
    service,
    recipient,
    subject,
    body,
    attachment_path=None,
    attachment_name=None,
):
    """
    Envoie un email individuel à un seul destinataire.
    """

    message = create_email(
        recipient=recipient,
        subject=subject,
        body=body,
        attachment_path=attachment_path,
        attachment_name=attachment_name,
    )

    return (
        service.users()
        .messages()
        .send(
            userId="me",
            body=message,
        )
        .execute()
    )