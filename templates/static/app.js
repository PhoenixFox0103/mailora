const getById = (id) => document.getElementById(id);

const personalizationCheckbox = getById("personalization");
const personalizationControl = getById("personalizationControl");
const modeMessage = getById("modeMessage");
const variableButtons = getById("variableButtons");
const subjectField = getById("subject");
const bodyField = getById("body");
const subjectPreview = getById("subjectPreview");
const bodyPreview = getById("bodyPreview");
const previewMode = getById("previewMode");
const attachmentInput = getById("attachment");
const attachmentName = getById("attachmentName");
const campaignForm = getById("campaignForm");
const notification = getById("notification");
const fileTab = getById("fileTab");
const directTab = getById("directTab");
const filePanel = getById("filePanel");
const directPanel = getById("directPanel");
const scheduledAtInput = getById("scheduledAt");
const scheduledTimezoneSelect = getById("scheduledTimezone");
const timezonePreviewText = getById("timezonePreviewText");
const scheduleButton = getById("scheduleButton");
const cancelScheduleButton = getById("cancelScheduleButton");
const scheduleStatus = getById("scheduleStatus");
const scheduledDateText = getById("scheduledDateText");

let statusTimer = null;

function showNotification(message, type = "success") {
    if (!notification) {
        return;
    }

    notification.textContent = message;
    notification.className = `notification ${type}`;

    window.setTimeout(() => {
        notification.classList.add("hidden");
    }, 5000);
}

function applySampleValues(text) {
    return text
        .replaceAll("{{Prenom}}", "Marie")
        .replaceAll("{{Entreprise}}", "Entreprise Exemple")
        .replaceAll("{{Poste}}", "Data Engineer");
}

function createGenericPreview(text) {
    return text
        .replaceAll("{{Prenom}}", "")
        .replaceAll("{{Entreprise}}", "")
        .replaceAll("{{Poste}}", "")
        .replace(/[ \t]+([,.])/g, "$1")
        .replace(/[ \t]{2,}/g, " ")
        .replace(/[ \t]+\n/g, "\n")
        .trim();
}

function updatePreview() {
    const enabled = personalizationCheckbox.checked;

    const subject = enabled
        ? applySampleValues(subjectField.value)
        : createGenericPreview(subjectField.value);

    const message = enabled
        ? applySampleValues(bodyField.value)
        : createGenericPreview(bodyField.value);

    subjectPreview.textContent = subject || "Sans objet";
    bodyPreview.textContent = message || "Votre message apparaîtra ici.";
    previewMode.textContent = enabled
        ? "Message personnalisé"
        : "Message identique";
}

function updatePersonalizationMode() {
    const enabled = personalizationCheckbox.checked;

    personalizationControl.classList.toggle("enabled", enabled);
    personalizationControl.classList.toggle("disabled", !enabled);
    modeMessage.classList.toggle("enabled", enabled);
    modeMessage.classList.toggle("disabled", !enabled);
    variableButtons.classList.toggle("disabled", !enabled);

    variableButtons.querySelectorAll("button").forEach((button) => {
        button.disabled = !enabled;
    });

    if (enabled) {
        modeMessage.innerHTML = `
            <span class="mode-icon" aria-hidden="true">✦</span>
            <span>
                <strong>Message personnalisé</strong>
                <small>
                    Le prénom, l’entreprise et le poste seront remplacés
                    automatiquement pour chaque contact.
                </small>
            </span>
        `;
    } else {
        modeMessage.innerHTML = `
            <span class="mode-icon" aria-hidden="true">○</span>
            <span>
                <strong>Message identique</strong>
                <small>
                    Le même contenu sera envoyé séparément à chaque destinataire.
                </small>
            </span>
        `;
    }

    updatePreview();
}

function insertVariable(variable) {
    if (!personalizationCheckbox.checked) {
        return;
    }

    const start = bodyField.selectionStart;
    const end = bodyField.selectionEnd;

    bodyField.value =
        bodyField.value.slice(0, start)
        + variable
        + bodyField.value.slice(end);

    const newPosition = start + variable.length;

    bodyField.focus();
    bodyField.setSelectionRange(newPosition, newPosition);
    updatePreview();
}

function setImportMode(useDirectInput) {
    fileTab.classList.toggle("active", !useDirectInput);
    directTab.classList.toggle("active", useDirectInput);
    filePanel.classList.toggle("hidden", useDirectInput);
    directPanel.classList.toggle("hidden", !useDirectInput);
}

function buildFormData() {
    return new FormData(campaignForm);
}

async function parseJsonResponse(response) {
    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("La réponse du serveur n'est pas au format JSON.");
    }

    if (!response.ok) {
        throw new Error(data.message || "Une erreur est survenue.");
    }

    return data;
}

async function sendTestEmail() {
    const testEmail = getById("testEmail").value.trim();
    const button = getById("testButton");

    if (!testEmail) {
        showNotification("Renseignez une adresse email de test.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Envoi du test...";

    try {
        const response = await fetch("/send-test", {
            method: "POST",
            body: buildFormData(),
        });

        const data = await parseJsonResponse(response);
        showNotification(data.message, "success");
    } catch (error) {
        showNotification(error.message, "error");
    } finally {
        button.disabled = false;
        button.innerHTML = '<span aria-hidden="true">▷</span> Envoyer un test';
    }
}

async function startCampaign() {
    if (!getById("authorizedUse").checked) {
        showNotification(
            "Confirmez l’utilisation responsable de la liste.",
            "error"
        );
        return;
    }

    const confirmed = window.confirm(
        "Lancer la campagne ? Chaque contact recevra un email individuel."
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch("/start-campaign", {
            method: "POST",
            body: buildFormData(),
        });

        const data = await parseJsonResponse(response);

        showNotification(data.message, "success");
        getById("progressSection").classList.remove("hidden");
        getById("stopButton").classList.remove("hidden");

        if (statusTimer) {
            window.clearInterval(statusTimer);
        }

        statusTimer = window.setInterval(refreshStatus, 1500);
        await refreshStatus();
    } catch (error) {
        showNotification(error.message, "error");
    }
}

async function stopCampaign() {
    try {
        const response = await fetch("/stop-campaign", {
            method: "POST",
        });

        const data = await parseJsonResponse(response);
        showNotification(data.message, "success");
    } catch (error) {
        showNotification(error.message, "error");
    }
}

function getSelectedTimezoneLabel() {
    const selectedOption =
        scheduledTimezoneSelect.options[
            scheduledTimezoneSelect.selectedIndex
        ];

    return selectedOption
        ? selectedOption.textContent.trim()
        : "";
}

function updateTimezonePreview() {
    if (!scheduledAtInput || !scheduledTimezoneSelect) {
        return;
    }

    const scheduledAt = scheduledAtInput.value;
    const timezoneLabel = getSelectedTimezoneLabel();

    if (!timezonePreviewText) {
        return;
    }

    if (!scheduledAt) {
        timezonePreviewText.textContent =
            `Fuseau sélectionné : ${timezoneLabel}`;
        return;
    }

    timezonePreviewText.textContent =
        `Envoi prévu le ${scheduledAt.replace("T", " ")} · ${timezoneLabel}`;
}

function showScheduledCampaign(scheduledDisplay) {
    scheduledDateText.textContent = scheduledDisplay;
    scheduleStatus.classList.remove("hidden");
    cancelScheduleButton.classList.remove("hidden");
    scheduleButton.classList.add("hidden");
    getById("startButton").disabled = true;
}

function hideScheduledCampaign() {
    scheduleStatus.classList.add("hidden");
    cancelScheduleButton.classList.add("hidden");
    scheduleButton.classList.remove("hidden");
    scheduledDateText.textContent = "";

    if (scheduleButton.dataset.hasContacts === "true") {
        scheduleButton.disabled = false;
        getById("startButton").disabled = false;
    }
}

async function scheduleCampaign() {
    if (!getById("authorizedUse").checked) {
        showNotification(
            "Confirmez l’utilisation responsable de la liste.",
            "error"
        );
        return;
    }

    const scheduledAt = scheduledAtInput.value;
    const timezoneLabel = getSelectedTimezoneLabel();

    if (!scheduledAt) {
        showNotification("Choisissez une date et une heure.", "error");
        return;
    }

    const confirmed = window.confirm(
        `Programmer cette campagne le ${scheduledAt.replace("T", " ")} `
        + `dans le fuseau ${timezoneLabel} ?`
    );

    if (!confirmed) {
        return;
    }

    scheduleButton.disabled = true;
    scheduleButton.textContent = "Programmation...";

    try {
        const response = await fetch("/schedule-campaign", {
            method: "POST",
            body: buildFormData(),
        });

        const data = await parseJsonResponse(response);

        showNotification(data.message, "success");
        showScheduledCampaign(data.scheduled_display);

        if (statusTimer) {
            window.clearInterval(statusTimer);
        }

        statusTimer = window.setInterval(refreshStatus, 1500);
    } catch (error) {
        showNotification(error.message, "error");
        scheduleButton.disabled = false;
    } finally {
        scheduleButton.innerHTML =
            '<span aria-hidden="true">◷</span> Programmer l\'envoi';
    }
}

async function cancelScheduledCampaign() {
    const confirmed = window.confirm(
        "Annuler la campagne programmée ?"
    );

    if (!confirmed) {
        return;
    }

    cancelScheduleButton.disabled = true;
    cancelScheduleButton.textContent = "Annulation...";

    try {
        const response = await fetch("/cancel-scheduled-campaign", {
            method: "POST",
        });

        const data = await parseJsonResponse(response);

        showNotification(data.message, "success");
        hideScheduledCampaign();

        if (statusTimer) {
            window.clearInterval(statusTimer);
            statusTimer = null;
        }
    } catch (error) {
        showNotification(error.message, "error");
    } finally {
        cancelScheduleButton.disabled = false;
        cancelScheduleButton.innerHTML =
            '<span aria-hidden="true">×</span> Annuler la programmation';
    }
}

function displayResults(results) {
    const resultList = getById("resultList");
    resultList.innerHTML = "";

    results.slice(-30).reverse().forEach((result) => {
        const row = document.createElement("div");
        const information = document.createElement("div");
        const email = document.createElement("strong");
        const message = document.createElement("small");
        const status = document.createElement("strong");

        row.className = "result-item";
        information.className = "result-information";
        email.textContent = result.email || "Erreur générale";
        message.textContent = result.message || "";
        status.className = result.status === "sent"
            ? "result-status sent"
            : "result-status failed";
        status.textContent = result.status === "sent"
            ? "Envoyé"
            : "Échec";

        information.appendChild(email);

        if (result.message) {
            information.appendChild(message);
        }

        row.append(information, status);
        resultList.appendChild(row);
    });
}

async function refreshStatus() {
    try {
        const response = await fetch("/campaign-status");
        const data = await response.json();

        if (data.status === "scheduled" && data.scheduled_display) {
            showScheduledCampaign(data.scheduled_display);
            return;
        }

        const total = Math.max(data.total || 0, 1);
        const percentage = Math.min(
            100,
            Math.round(((data.processed || 0) / total) * 100)
        );

        getById("progressText").textContent =
            `${data.processed || 0} / ${data.total || 0}`;
        getById("progressPercent").textContent = `${percentage} %`;
        getById("progressBar").style.width = `${percentage}%`;
        getById("currentEmail").textContent = data.current_email
            ? `Traitement : ${data.current_email}`
            : "";
        getById("sentCount").textContent =
            `${data.sent || 0} envoyé(s)`;
        getById("failedCount").textContent =
            `${data.failed || 0} échec(s)`;

        displayResults(data.results || []);

        if (data.status === "running") {
            getById("progressSection").classList.remove("hidden");
            getById("stopButton").classList.remove("hidden");
            scheduleStatus.classList.add("hidden");
            cancelScheduleButton.classList.add("hidden");
            scheduleButton.classList.add("hidden");
        }

        if (["completed", "stopped", "error"].includes(data.status)) {
            if (statusTimer) {
                window.clearInterval(statusTimer);
                statusTimer = null;
            }

            getById("stopButton").classList.add("hidden");
        }
    } catch (error) {
        console.error("Erreur de suivi :", error);
    }
}

function resetCampaignDisplay() {
    getById("progressSection").classList.add("hidden");
    getById("stopButton").classList.add("hidden");
    getById("progressText").textContent = "0 / 0";
    getById("progressPercent").textContent = "0 %";
    getById("progressBar").style.width = "0%";
    getById("currentEmail").textContent = "";
    getById("sentCount").textContent = "0 envoyé(s)";
    getById("failedCount").textContent = "0 échec(s)";
    getById("resultList").innerHTML = "";
}

fileTab.addEventListener("click", () => setImportMode(false));
directTab.addEventListener("click", () => setImportMode(true));
personalizationCheckbox.addEventListener(
    "change",
    updatePersonalizationMode
);
subjectField.addEventListener("input", updatePreview);
bodyField.addEventListener("input", updatePreview);

variableButtons.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
        insertVariable(button.dataset.variable);
    });
});

attachmentInput.addEventListener("change", () => {
    const selectedFile = attachmentInput.files[0];
    attachmentName.textContent = selectedFile
        ? selectedFile.name
        : "PDF, Word ou image, optionnel";
});

scheduledAtInput.addEventListener("change", updateTimezonePreview);
scheduledAtInput.addEventListener("input", updateTimezonePreview);
scheduledTimezoneSelect.addEventListener("change", updateTimezonePreview);

getById("testButton").addEventListener("click", sendTestEmail);
getById("startButton").addEventListener("click", startCampaign);
getById("stopButton").addEventListener("click", stopCampaign);
scheduleButton.addEventListener("click", scheduleCampaign);
cancelScheduleButton.addEventListener("click", cancelScheduledCampaign);

scheduleButton.dataset.hasContacts = scheduleButton.disabled
    ? "false"
    : "true";

setImportMode(false);
updatePersonalizationMode();
updatePreview();
updateTimezonePreview();
resetCampaignDisplay();
refreshStatus();
