pipeline {
    agent any

    environment {
        // GitHub Token credential configured in Jenkins Credentials Manager
        GH_TOKEN = credentials('github-release-token')
        GITHUB_TOKEN = credentials('github-release-token')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
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
                        env.APP_VERSION = "v" + versionMatch[0][1]
                    } else {
                        env.APP_VERSION = "v1.0.0"
                    }
                    echo "Target Release Version: ${env.APP_VERSION}"
                }
            }
        }

        stage('Package Desktop EXE & Publish Update') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            npx electron-builder --config electron-builder.json --publish always
                        '''
                    } else {
                        bat '''
                            @echo off
                            call npx electron-builder --config electron-builder.json --publish always
                            exit /b %ERRORLEVEL%
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            // Archive installer, portable binary, and latest.yml auto-updater manifest
            archiveArtifacts artifacts: 'dist-electron/*.exe, dist-electron/latest.yml', fingerprint: true, allowEmptyArchive: true
        }
        success {
            echo "Successfully built and published EmpMonitor Desktop Suite ${env.APP_VERSION}"
        }
        failure {
            echo "Jenkins build failed. Check console output for diagnostic details."
        }
    }
}
