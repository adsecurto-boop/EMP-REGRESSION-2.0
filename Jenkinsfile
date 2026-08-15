pipeline {
    agent any

    environment {
        // Cloudflare R2 S3-Compatible Endpoint & Bucket Configuration
        // Jurisdiction Endpoints for S3 Clients:
        //   - Default (Global): https://ca2a4c1cb15c70abc670f34aecbd5084.r2.cloudflarestorage.com
        //   - European Union (EU): https://ca2a4c1cb15c70abc670f34aecbd5084.eu.r2.cloudflarestorage.com
        R2_ACCOUNT_ID = "ca2a4c1cb15c70abc670f34aecbd5084"
        R2_ENDPOINT_DEFAULT = "https://ca2a4c1cb15c70abc670f34aecbd5084.r2.cloudflarestorage.com"
        R2_ENDPOINT_EU = "https://ca2a4c1cb15c70abc670f34aecbd5084.eu.r2.cloudflarestorage.com"
        R2_ENDPOINT = "https://ca2a4c1cb15c70abc670f34aecbd5084.r2.cloudflarestorage.com" // Set to R2_ENDPOINT_EU for EU data residency
        R2_BUCKET = "s3://empmonitor-updates"
        BASE_URL = "https://updates.yourdomain.com"
        AWS_DEFAULT_REGION = "auto"

        // Node.js & electron-builder networking fixes for CI runners
        NODE_OPTIONS = "--dns-result-order=ipv4first"
        CSC_IDENTITY_AUTO_DISCOVERY = "false"
        WIN_CSC_IDENTITY_AUTO_DISCOVERY = "false"
        ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
        ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
    }

    stages {
        stage('Git Metadata & Build Info') {
            steps {
                script {
                    try {
                        if (isUnix()) {
                            env.GIT_COMMIT_HASH = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                            env.GIT_COMMIT_MSG = sh(script: 'git log -1 --format=%s', returnStdout: true).trim()
                            env.GIT_AUTHOR = sh(script: 'git log -1 --format="%an <%ae>"', returnStdout: true).trim()
                            env.GIT_BRANCH_NAME = sh(script: 'git rev-parse --abbrev-ref HEAD', returnStdout: true).trim()
                        } else {
                            env.GIT_COMMIT_HASH = bat(script: '@git rev-parse --short HEAD', returnStdout: true).trim().split('[\r\n]+').last().trim()
                            env.GIT_COMMIT_MSG = bat(script: '@git log -1 --format=%%s', returnStdout: true).trim().split('[\r\n]+').last().trim()
                            env.GIT_AUTHOR = bat(script: '@git log -1 --format=%%an', returnStdout: true).trim().split('[\r\n]+').last().trim()
                            env.GIT_BRANCH_NAME = bat(script: '@git rev-parse --abbrev-ref HEAD', returnStdout: true).trim().split('[\r\n]+').last().trim()
                        }
                    } catch (Exception exc) {
                        echo "Warning during git extraction: ${exc}. Using fallback environment variables."
                    }

                    if (!env.GIT_COMMIT_HASH) {
                        env.GIT_COMMIT_HASH = env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : "HEAD"
                    }
                    if (!env.GIT_COMMIT_MSG) {
                        env.GIT_COMMIT_MSG = "Automated release build"
                    }
                    if (!env.GIT_BRANCH_NAME) {
                        env.GIT_BRANCH_NAME = env.BRANCH_NAME ?: "main"
                    }
                    if (!env.GIT_AUTHOR) {
                        env.GIT_AUTHOR = "EmpMonitor QA Team"
                    }

                    echo "=== JENKINS GIT BUILD DATA ==="
                    echo "Branch: ${env.GIT_BRANCH_NAME}"
                    echo "Commit Hash: ${env.GIT_COMMIT_HASH}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Commit Message: ${env.GIT_COMMIT_MSG}"
                    echo "==============================="
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            npm install --force
                        '''
                    } else {
                        bat '''
                            @echo off
                            if exist package-lock.json del /f /q package-lock.json
                            call npm install --force
                            call npm install --no-save @tailwindcss/oxide-win32-x64-msvc @rollup/rollup-win32-x64-msvc lightningcss-win32-x64-msvc @esbuild/win32-x64
                            exit /b 0
                        '''
                    }
                }
            }
        }

        stage('Build Web & Backend Server') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'npm run build'
                    } else {
                        bat '''
                            @echo off
                            call npm run build
                            exit /b %ERRORLEVEL%
                        '''
                    }
                }
            }
        }

        stage('Extract App Version') {
            steps {
                script {
                    // Pure Groovy extraction: works on all platforms without subprocess execution
                    def pkgContent = readFile('package.json')
                    def versionMatch = pkgContent =~ /"version":\s*"([^"]+)"/
                    if (versionMatch) {
                        env.RAW_VERSION = versionMatch[0][1]
                        env.APP_VERSION = "v" + versionMatch[0][1]
                    } else {
                        env.RAW_VERSION = "1.0.0"
                        env.APP_VERSION = "v1.0.0"
                    }
                    echo "Target Release Version: ${env.APP_VERSION} (Raw: ${env.RAW_VERSION})"
                    
                    // Set Jenkins Build Display and Description with Git Commit Message
                    currentBuild.displayName = "#${BUILD_NUMBER} - ${env.APP_VERSION}"
                    currentBuild.description = "Commit [${env.GIT_COMMIT_HASH}]: ${env.GIT_COMMIT_MSG}"
                }
            }
        }

        stage('Package Desktop Binary') {
            steps {
                script {
                    echo "Packaging Electron Windows Executable Installer and Portable Binary..."
                    if (isUnix()) {
                        sh '''
                            export CSC_IDENTITY_AUTO_DISCOVERY=false
                            export WIN_CSC_IDENTITY_AUTO_DISCOVERY=false
                            export ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"
                            export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
                            npx electron-builder --config electron-builder.json -c.npmRebuild=false --publish never
                        '''
                    } else {
                        bat '''
                            @echo off
                            set CSC_IDENTITY_AUTO_DISCOVERY=false
                            set WIN_CSC_IDENTITY_AUTO_DISCOVERY=false
                            set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
                            set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
                            set NODE_OPTIONS=--dns-result-order=ipv4first
                            call npx electron-builder --config electron-builder.json -c.npmRebuild=false --publish never
                            exit /b %ERRORLEVEL%
                        '''
                    }
                }
            }
        }

        stage('Publish to Cloudflare R2') {
            steps {
                script {
                    echo "Publishing binaries and auto-update manifest to Cloudflare R2 bucket (${R2_BUCKET})..."
                    
                    withCredentials([usernamePassword(
                        credentialsId: 'cloudflare-r2-creds',
                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                        passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                    )]) {
                        if (isUnix()) {
                            sh '''
                                set -e
                                # 1. Locate generated Windows installer executable
                                BINARY_EXE=$(find dist-electron -maxdepth 1 -name "*.exe" | head -n 1)
                                if [ -z "$BINARY_EXE" ]; then
                                    echo "ERROR: No .exe binary found in dist-electron/"
                                    exit 1
                                fi
                                BINARY_NAME=$(basename "$BINARY_EXE")
                                echo "Selected binary for release: ${BINARY_EXE} (${BINARY_NAME})"

                                # 2. Generate latest.json manifest with SHA-256 and release metadata
                                node scripts/generate_update_manifest.mjs \
                                    --binary-path "$BINARY_EXE" \
                                    --version "${RAW_VERSION}" \
                                    --base-url "${BASE_URL}" \
                                    --output-manifest "dist-electron/latest.json" \
                                    --notes "Automated release build for commit ${GIT_COMMIT_HASH}: ${GIT_COMMIT_MSG}"

                                # 3. Upload Binary Executable to Cloudflare R2 (Immutable Long-Term Cache)
                                echo "Uploading ${BINARY_NAME} to Cloudflare R2..."
                                aws s3 cp "$BINARY_EXE" "${R2_BUCKET}/${BINARY_NAME}" \
                                    --endpoint-url "${R2_ENDPOINT}" \
                                    --cache-control "public, max-age=31536000, immutable"

                                # 4. Upload latest.json Manifest (Strict No-Cache Policy)
                                echo "Uploading latest.json manifest to Cloudflare R2..."
                                aws s3 cp "dist-electron/latest.json" "${R2_BUCKET}/latest.json" \
                                    --endpoint-url "${R2_ENDPOINT}" \
                                    --cache-control "no-cache, no-store, must-revalidate"

                                echo "Cloudflare R2 auto-update release complete: ${BASE_URL}/latest.json"
                            '''
                        } else {
                            bat '''
                                @echo off
                                setlocal enabledelayedexpansion

                                :: 1. Locate generated Windows installer executable
                                set "BINARY_EXE="
                                for %%F in (dist-electron\\*.exe) do (
                                    if not defined BINARY_EXE set "BINARY_EXE=%%F"
                                )

                                if not defined BINARY_EXE (
                                    echo ERROR: No .exe binary found in dist-electron\\
                                    exit /b 1
                                )

                                for %%I in ("%BINARY_EXE%") do set "BINARY_NAME=%%~nxI"
                                echo Selected binary for release: %BINARY_EXE% (%BINARY_NAME%)

                                :: 2. Generate latest.json manifest with SHA-256 and release metadata
                                node scripts\\generate_update_manifest.mjs ^
                                    --binary-path "%BINARY_EXE%" ^
                                    --version "%RAW_VERSION%" ^
                                    --base-url "%BASE_URL%" ^
                                    --output-manifest "dist-electron\\latest.json" ^
                                    --notes "Automated release build for commit %GIT_COMMIT_HASH%: %GIT_COMMIT_MSG%"
                                if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

                                :: 3. Upload Binary Executable to Cloudflare R2 (Immutable Long-Term Cache)
                                echo Uploading %BINARY_NAME% to Cloudflare R2...
                                aws s3 cp "%BINARY_EXE%" "%R2_BUCKET%/%BINARY_NAME%" ^
                                    --endpoint-url "%R2_ENDPOINT%" ^
                                    --cache-control "public, max-age=31536000, immutable"
                                if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

                                :: 4. Upload latest.json Manifest (Strict No-Cache Policy)
                                echo Uploading latest.json manifest to Cloudflare R2...
                                aws s3 cp "dist-electron\\latest.json" "%R2_BUCKET%/latest.json" ^
                                    --endpoint-url "%R2_ENDPOINT%" ^
                                    --cache-control "no-cache, no-store, must-revalidate"
                                if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

                                echo Cloudflare R2 auto-update release complete: %BASE_URL%/latest.json
                            '''
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            // Archive installer, portable binary, and latest.json auto-updater manifest
            archiveArtifacts artifacts: 'dist-electron/*.exe, dist-electron/latest.json, dist-electron/latest.yml', fingerprint: true, allowEmptyArchive: true
        }
        success {
            echo "Successfully built and published EmpMonitor Desktop Suite ${env.APP_VERSION} to Cloudflare R2 for commit '${env.GIT_COMMIT_MSG}'"
        }
        failure {
            echo "Jenkins build failed. Check console output for diagnostic details."
        }
    }
}
