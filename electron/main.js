const { app, BrowserWindow, ipcMain, Tray, nativeImage, clipboard } = require("electron");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { spawn } = require("child_process");

const HISTORY_PATH = path.join(os.homedir(), ".config", "rawspeak", "history.jsonl");
let backend = null;
let historyWatcher = null;
let statusTray = null;
let idleHideTimer = null;

app.setName("RawSpeak");

function createCircleTrayImage(hexColor) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="7" fill="${hexColor}" />
    </svg>
  `;
  const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
  return nativeImage.createFromDataURL(dataUrl);
}

function ensureTray() {
  if (!statusTray) {
    statusTray = new Tray(nativeImage.createEmpty());
    statusTray.setToolTip("RawSpeak");
  }
}

function hideTray() {
  if (idleHideTimer) {
    clearTimeout(idleHideTimer);
    idleHideTimer = null;
  }
  if (statusTray) {
    statusTray.destroy();
    statusTray = null;
  }
}

function setTrayState(state) {
  if (idleHideTimer) {
    clearTimeout(idleHideTimer);
    idleHideTimer = null;
  }

  // Keep tray indicator visible while actively recording/processing.
  // For idle/done, show blue briefly then hide.
  const palette = {
    listening: { color: "#ef4444", tooltip: "RawSpeak — listening", symbol: "🔴" },
    processing: { color: "#f59e0b", tooltip: "RawSpeak — processing", symbol: "🟠" },
    idle: { color: "#3b82f6", tooltip: "RawSpeak — idle", symbol: "🔵" },
  };
  const info = palette[state] || palette.idle;

  ensureTray();
  statusTray.setImage(createCircleTrayImage(info.color));
  statusTray.setTitle(info.symbol);
  statusTray.setToolTip(info.tooltip);

  if (state === "idle") {
    idleHideTimer = setTimeout(() => {
      hideTray();
    }, 1200);
  }
}

function updateStatusFromLogLine(line) {
  const msg = line.toLowerCase();
  if (msg.includes("recording started")) {
    setTrayState("listening");
    return;
  }
  if (msg.includes("recording stopped") || msg.includes("processing audio")) {
    setTrayState("processing");
    return;
  }
  if (
    msg.includes("done!") ||
    msg.includes("empty transcription") ||
    msg.includes("recording too short") ||
    msg.includes("error in pipeline")
  ) {
    setTrayState("idle");
  }
}

function parseHistory(limit = 300) {
  if (!fs.existsSync(HISTORY_PATH)) return [];
  const lines = fs
    .readFileSync(HISTORY_PATH, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const entries = [];
  for (const line of lines) {
    try {
      const obj = JSON.parse(line);
      if (!obj.text || !String(obj.text).trim()) continue;
      entries.push({
        timestamp: obj.timestamp || "--",
        text: String(obj.text),
      });
    } catch {
      // ignore malformed line
    }
  }
  return entries.slice(-limit).reverse();
}

function spawnBackend() {
  if (backend) return;
  const repoRoot = path.resolve(__dirname, "..");
  const venvPython = path.join(repoRoot, ".venv", "bin", "python");
  const pythonBin = fs.existsSync(venvPython) ? venvPython : "python3";

  backend = spawn(pythonBin, ["-m", "rawspeak.main", "run-headless"], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });

  const handleBackendOutput = (chunk, isError = false) => {
    const text = chunk.toString();
    for (const line of text.split("\n")) {
      const msg = line.trim();
      if (!msg) continue;
      if (isError) {
        console.error(`[rawspeak:error] ${msg}`);
      } else {
        console.log(`[rawspeak] ${msg}`);
      }
      updateStatusFromLogLine(msg);
    }
  };

  // Python logging defaults to stderr, so parse both streams.
  backend.stdout.on("data", (chunk) => handleBackendOutput(chunk, false));
  backend.stderr.on("data", (chunk) => handleBackendOutput(chunk, true));

  backend.on("exit", (code) => {
    console.log(`[rawspeak] backend exited with code ${code}`);
    backend = null;
  });
}

function stopBackend() {
  if (!backend) return;
  backend.kill();
  backend = null;
  hideTray();
}

function watchHistory(win) {
  if (historyWatcher) historyWatcher.close();
  const historyDir = path.dirname(HISTORY_PATH);
  fs.mkdirSync(historyDir, { recursive: true });

  historyWatcher = fs.watch(historyDir, { persistent: false }, (_evt, filename) => {
    if (filename && filename !== path.basename(HISTORY_PATH)) return;
    if (!win || win.isDestroyed()) return;
    win.webContents.send("history-updated", parseHistory());
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 980,
    height: 640,
    minWidth: 720,
    minHeight: 420,
    title: "RawSpeak",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "renderer", "index.html"));
  watchHistory(win);
  return win;
}

ipcMain.handle("history-list", async () => parseHistory());
ipcMain.handle("history-copy", async (_event, text) => {
  clipboard.writeText(String(text || ""));
  return true;
});

app.whenReady().then(() => {
  const logoPath = path.resolve(__dirname, "..", "assets", "rawspeak_logo.png");
  if (process.platform === "darwin" && app.dock && fs.existsSync(logoPath)) {
    app.dock.setIcon(logoPath);
  }

  spawnBackend();
  const win = createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });

  win.on("closed", () => {
    if (historyWatcher) {
      historyWatcher.close();
      historyWatcher = null;
    }
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});
