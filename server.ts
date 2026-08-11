import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { exec } from "child_process";
import fs from "fs";

// Safe directory determination supporting ESM, bundled CJS, and Electron app.asar
let currentDir = process.cwd();
try {
  if (typeof __dirname !== "undefined") {
    currentDir = __dirname;
  } else if (import.meta && import.meta.url) {
    currentDir = path.dirname(fileURLToPath(import.meta.url));
  }
} catch {
  // fallback
}

let ROOT_DIR = (currentDir.endsWith("dist") || currentDir.endsWith("dist" + path.sep))
  ? path.resolve(currentDir, "..")
  : currentDir;

if (!fs.existsSync(path.join(ROOT_DIR, "config")) && fs.existsSync(path.join(process.cwd(), "config"))) {
  ROOT_DIR = process.cwd();
}

async function startServer() {
  const app = express();
  const PORT = process.env.PORT || 3000;

  app.use(express.json());

  // CORS middleware for Electron desktop app and local requests
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    if (req.method === "OPTIONS") {
      return res.sendStatus(200);
    }
    next();
  });

  // API to trigger framework test run
  app.post("/api/run", (req, res) => {
    const { plugin, environment, checkOnly } = req.body || {};
    const pythonExe = process.platform === "win32" ? "python" : "python3";
    let cmd = `${pythonExe} run.py`;
    
    if (checkOnly) {
      cmd += " --check";
    } else {
      if (environment) {
        cmd += ` --environment ${environment}`;
      }
      if (plugin) {
        cmd += ` --plugin ${plugin}`;
      }
    }

    exec(cmd, { cwd: ROOT_DIR }, (error, stdout, stderr) => {
      let reportData = null;
      try {
        const reportsDir = path.join(ROOT_DIR, "reports");
        if (fs.existsSync(reportsDir)) {
          const subdirs = fs.readdirSync(reportsDir).sort().reverse();
          if (subdirs.length > 0) {
            const latestReportPath = path.join(reportsDir, subdirs[0], "report.json");
            if (fs.existsSync(latestReportPath)) {
              reportData = JSON.parse(fs.readFileSync(latestReportPath, "utf-8"));
            }
          }
        }
      } catch (e) {
        console.error("Error reading report JSON:", e);
      }

      res.json({
        success: !error || error.code === 0,
        exitCode: error ? error.code : 0,
        stdout,
        stderr,
        report: reportData
      });
    });
  });

  // API to get feature profiles
  app.get("/api/features", (req, res) => {
    try {
      const featuresPath = path.join(ROOT_DIR, "config", "features.json");
      if (fs.existsSync(featuresPath)) {
        const data = JSON.parse(fs.readFileSync(featuresPath, "utf-8"));
        res.json(data.profiles || []);
      } else {
        res.json([]);
      }
    } catch (err) {
      res.status(500).json({ error: "Failed to read features config" });
    }
  });

  // API to get framework details
  app.get("/api/framework", (req, res) => {
    try {
      const fwPath = path.join(ROOT_DIR, "config", "framework.json");
      if (fs.existsSync(fwPath)) {
        const data = JSON.parse(fs.readFileSync(fwPath, "utf-8"));
        res.json(data);
      } else {
        res.json({});
      }
    } catch (err) {
      res.status(500).json({ error: "Failed to read framework config" });
    }
  });

  // API to get Desktop App & Chrome Browser Environment status
  app.get("/api/desktop/status", (req, res) => {
    const playwrightProfileExists = fs.existsSync(path.join(ROOT_DIR, "playwright-profile"));
    const recordingsDir = path.join(ROOT_DIR, "recordings");
    const recordingsCount = fs.existsSync(recordingsDir)
      ? fs.readdirSync(recordingsDir).filter(f => f.endsWith(".py")).length
      : 0;

    res.json({
      environment: "EmpMonitor Integrated Runtime Environment",
      chromeProfileAvailable: playwrightProfileExists,
      playwrightProfilePath: "playwright-profile",
      recordingsAvailable: recordingsCount,
      githubRepo: "adsecurto-boop/Emp_Regression_suite",
      autoUpdaterProvider: "GitHub Releases (electron-updater)",
      buildTarget: "Windows x64 Desktop (.exe installer & portable)"
    });
  });

  // API to run Chrome Browser Dashboard validation script
  app.post("/api/chrome/launch-check", (req, res) => {
    const { recordingScript } = req.body || {};
    const scriptToRun = recordingScript || "002_dashboard_home.py";
    const scriptPath = path.join(ROOT_DIR, "recordings", scriptToRun);

    if (!fs.existsSync(scriptPath)) {
      return res.status(404).json({ error: `Recording script ${scriptToRun} not found.` });
    }

    const pythonExe = process.platform === "win32" ? "python" : "python3";
    const cmd = `${pythonExe} recordings/${scriptToRun}`;
    exec(cmd, { cwd: ROOT_DIR }, (error, stdout, stderr) => {
      res.json({
        success: !error || error.code === 0,
        scriptExecuted: scriptToRun,
        stdout,
        stderr: stderr || (error ? error.message : "")
      });
    });
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(ROOT_DIR, "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  const server = app.listen(Number(PORT), "0.0.0.0", () => {
    console.log(`Server running on http://127.0.0.1:${PORT}`);
  });

  server.on("error", (err: any) => {
    if (err && err.code === "EADDRINUSE") {
      console.log(`Port ${PORT} is already in use. Reusing existing server instance.`);
    } else {
      console.error("Express server error:", err);
    }
  });
}

startServer();
