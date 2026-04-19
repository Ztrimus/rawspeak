let toastTimer = null;

async function copyToClipboard(text) {
  await window.rawspeak.copyText(text || "");
  showToast("Copied");
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 900);
}

function renderRows(entries) {
  const body = document.getElementById("history-body");
  const empty = document.getElementById("empty");
  const totalCount = document.getElementById("total-count");
  const todayCount = document.getElementById("today-count");
  body.innerHTML = "";

  const list = entries || [];
  totalCount.textContent = String(list.length);
  todayCount.textContent = String(list.length);

  if (list.length === 0) {
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  for (const entry of list) {
    const tr = document.createElement("tr");
    const tdTime = document.createElement("td");
    const tdText = document.createElement("td");
    const tdActions = document.createElement("td");
    tdTime.textContent = entry.timestamp || "--";
    tdText.textContent = entry.text || "";
    tdTime.className = "time-cell";
    tdText.className = "text-cell";

    const wrap = document.createElement("div");
    wrap.className = "row-actions";
    const copyBtn = document.createElement("button");
    copyBtn.className = "icon-btn";
    copyBtn.type = "button";
    copyBtn.title = "Copy";
    copyBtn.ariaLabel = "Copy";
    copyBtn.textContent = "⧉";
    copyBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await copyToClipboard(entry.text || "");
    });
    wrap.appendChild(copyBtn);
    tdActions.appendChild(wrap);

    tr.addEventListener("click", async () => {
      await copyToClipboard(entry.text || "");
    });

    tr.appendChild(tdTime);
    tr.appendChild(tdText);
    tr.appendChild(tdActions);
    body.appendChild(tr);
  }
}

async function boot() {
  const entries = await window.rawspeak.listHistory();
  renderRows(entries);
  window.rawspeak.onHistoryUpdated((nextEntries) => {
    renderRows(nextEntries);
  });
}

boot();
