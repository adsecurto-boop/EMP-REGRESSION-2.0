import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';

interface CliArgs {
  binaryPath: string;
  version: string;
  baseUrl: string;
  outputManifest: string;
  bucket: string;
  endpoint: string;
  notes: string;
  channel: string;
  mandatory: boolean;
}

function parseArgs(): CliArgs {
  const args = process.argv.slice(2);
  let binaryPath = '';
  let version = process.env.RAW_VERSION || process.env.APP_VERSION || '';
  let baseUrl = process.env.BASE_URL || '';
  let outputManifest = 'dist-electron/latest.json';
  let bucket = process.env.R2_BUCKET || '';
  let endpoint = process.env.R2_ENDPOINT || '';
  let notes = '';
  let channel = 'stable';
  let mandatory = false;

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
    } else if (arg === '--bucket' && i + 1 < args.length) {
      bucket = args[++i];
    } else if (arg === '--endpoint' && i + 1 < args.length) {
      endpoint = args[++i];
    } else if (arg === '--notes' && i + 1 < args.length) {
      notes = args[++i];
    } else if (arg === '--channel' && i + 1 < args.length) {
      channel = args[++i];
    } else if (arg === '--mandatory') {
      mandatory = true;
    }
  }

  // Fallback scan dist-electron if binary-path not provided
  if (!binaryPath) {
    const distDir = path.resolve(process.cwd(), 'dist-electron');
    if (fs.existsSync(distDir)) {
      const exes = fs.readdirSync(distDir).filter(f => f.endsWith('.exe'));
      if (exes.length > 0) {
        binaryPath = path.join('dist-electron', exes[0]);
      }
    }
  }

  return { binaryPath, version, baseUrl, outputManifest, bucket, endpoint, notes, channel, mandatory };
}

function computeSha256(filePath: string): string {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex').toLowerCase();
}

async function uploadToS3(client: S3Client, bucketName: string, key: string, filePath: string, contentType: string, cacheControl: string) {
  const fileStream = fs.createReadStream(filePath);
  const command = new PutObjectCommand({
    Bucket: bucketName,
    Key: key,
    Body: fileStream,
    ContentType: contentType,
    CacheControl: cacheControl
  });
  await client.send(command);
  console.log(`Successfully uploaded: ${key} to ${bucketName}`);
}

async function main() {
  const opts = parseArgs();

  if (!opts.binaryPath) {
    console.error('ERROR: No .exe binary found or specified.');
    process.exit(1);
  }

  const resolvedBinary = path.resolve(process.cwd(), opts.binaryPath);
  if (!fs.existsSync(resolvedBinary)) {
    console.error(`ERROR: Binary file not found: ${resolvedBinary}`);
    process.exit(1);
  }

  const fileName = path.basename(resolvedBinary);
  const cleanVersion = opts.version.replace(/^v/, '');
  const sha256 = computeSha256(resolvedBinary);
  const stats = fs.statSync(resolvedBinary);
  const cleanBaseUrl = opts.baseUrl.replace(/\/+$/, '');
  const downloadUrl = `${cleanBaseUrl}/${fileName}`;
  const releaseDate = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const releaseNotes = opts.notes || `EmpMonitor Desktop Suite ${cleanVersion} automated release build.`;

  // Generate latest.json
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
  console.log(`Generated manifest: ${outputResolved}`);
  console.log(JSON.stringify(manifest, null, 2));

  // Determine S3 bucket name (clean s3:// prefix if passed)
  const bucketName = opts.bucket.replace(/^s3:\/\//, '');

  const accessKeyId = process.env.AWS_ACCESS_KEY_ID;
  const secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;

  if (accessKeyId && secretAccessKey && bucketName && opts.endpoint) {
    console.log(`Initializing Cloudflare R2 client (endpoint: ${opts.endpoint}, bucket: ${bucketName})...`);
    const s3 = new S3Client({
      region: 'auto',
      endpoint: opts.endpoint,
      credentials: {
        accessKeyId,
        secretAccessKey
      }
    });

    console.log(`Uploading executable (${fileName}, ${(stats.size / 1024 / 1024).toFixed(2)} MB)...`);
    await uploadToS3(s3, bucketName, fileName, resolvedBinary, 'application/vnd.microsoft.portable-executable', 'public, max-age=31536000, immutable');

    console.log('Uploading latest.json manifest...');
    await uploadToS3(s3, bucketName, 'latest.json', outputResolved, 'application/json', 'no-cache, no-store, must-revalidate');

    console.log(`\nRelease successfully published to Cloudflare R2: ${downloadUrl}`);
  } else {
    console.log('Skipping S3 upload (credentials or endpoint not provided in environment).');
  }
}

main().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
