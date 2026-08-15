import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function parseArgs() {
  const args = process.argv.slice(2);
  let binaryPath = '';
  let version = '';
  let baseUrl = '';
  let outputManifest = 'dist-electron/latest.json';
  let mandatory = false;
  let notes = '';
  let channel = 'stable';

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--binary-path' && i + 1 < args.length) {
      binaryPath = args[++i];
    } else if (arg === '--version' && i + 1 < args.length) {
      version = args[++i];
    } else if (arg === '--base-url' && i + 1 < args.length) {
      baseUrl = args[++i];
    } else if (arg === '--output-manifest' && i + 1 < args.length) {
      outputManifest = args[++i];
    } else if (arg === '--mandatory') {
      mandatory = true;
    } else if (arg === '--notes' && i + 1 < args.length) {
      notes = args[++i];
    } else if (arg === '--channel' && i + 1 < args.length) {
      channel = args[++i];
    }
  }

  if (!binaryPath || !version || !baseUrl) {
    console.error('Usage: node scripts/generate_update_manifest.mjs --binary-path <file> --version <ver> --base-url <url> [--output-manifest <file>] [--notes <notes>] [--channel <chan>] [--mandatory]');
    process.exit(1);
  }

  return { binaryPath, version, baseUrl, outputManifest, mandatory, notes, channel };
}

function computeSha256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex').toLowerCase();
}

function main() {
  const opts = parseArgs();
  const resolvedBinary = path.resolve(process.cwd(), opts.binaryPath);

  if (!fs.existsSync(resolvedBinary)) {
    console.error(`Binary target not found at: ${resolvedBinary}`);
    process.exit(1);
  }

  const cleanVersion = opts.version.replace(/^v/, '');
  const sha256 = computeSha256(resolvedBinary);
  const stats = fs.statSync(resolvedBinary);
  const fileName = path.basename(resolvedBinary);
  const cleanBaseUrl = opts.baseUrl.replace(/\/+$/, '');
  const downloadUrl = `${cleanBaseUrl}/${fileName}`;
  const releaseDate = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const releaseNotes = opts.notes || `EmpMonitor Desktop Suite ${cleanVersion} automated release build.`;

  const manifest = {
    version: cleanVersion,
    release_date: releaseDate,
    url: downloadUrl,
    sha256,
    mandatory: opts.mandatory,
    notes: releaseNotes,
    file_size_bytes: stats.size,
    channel: opts.channel
  };

  const outputResolved = path.resolve(process.cwd(), opts.outputManifest);
  const outputDir = path.dirname(outputResolved);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(outputResolved, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
  console.log(`Successfully generated auto-update manifest at: ${outputResolved}`);
  console.log(JSON.stringify(manifest, null, 2));
}

main();
