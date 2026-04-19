const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("rawspeak", {
  listHistory: () => ipcRenderer.invoke("history-list"),
  copyText: (text) => ipcRenderer.invoke("history-copy", text),
  onHistoryUpdated: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("history-updated", handler);
    return () => ipcRenderer.removeListener("history-updated", handler);
  },
});
