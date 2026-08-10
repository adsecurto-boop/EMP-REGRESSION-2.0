import express from "express";
import path from "path";
import { exec } from "child_process";
import { createServer as createViteServer } from "vite";
import fs from "fs";

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // API to trigger framework test run
  app.post("/api/run", (req, res) => {
    const { plugin, environment, checkOnly } = req.body || {};
    let cmd = "python3 run.py";
    
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

    exec(cmd, { cwd: process.cwd() }, (error, stdout, stderr) => {
      let reportData = null;
      try {
        // Try to find latest report json in reports/ directory if generated
        const reportsDir = path.join(process.cwd(), "reports");
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
      const featuresPath = path.join(process.cwd(), "config", "features.json");
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
      const fwPath = path.join(process.cwd(), "config", "framework.json");
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
    const playwrightProfileExists = fs.existsSync(path.join(process.cwd(), "playwright-profile"));
    const recordingsCount = fs.existsSync(path.join(process.cwd(), "recordings"))
      ? fs.readdirSync(path.join(process.cwd(), "recordings")).filter(f => f.endsWith(".py")).length
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
    const scriptPath = path.join(process.cwd(), "recordings", scriptToRun);

    if (!fs.existsSync(scriptPath)) {
      return res.status(404).json({ error: `Recording script ${scriptToRun} not found.` });
    }

    const cmd = `python3 recordings/${scriptToRun}`;
    exec(cmd, { cwd: process.cwd() }, (error, stdout, stderr) => {
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
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
