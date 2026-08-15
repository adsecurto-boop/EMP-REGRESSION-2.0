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
                            pip3 install playwright requests || pip install playwright requests
                        '''
                    } else {
                        bat '''
                            if exist package-lock.json del /f /q package-lock.json
                            call npm install --force
                            call npm install --no-save @tailwindcss/oxide-win32-x64-msvc @rollup/rollup-win32-x64-msvc lightningcss-win32-x64-msvc @esbuild/win32-x64
                            call pip install playwright requests
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
                        bat 'call npm run build'
                    }
                }
            }
        }

        stage('Extract App Version') {
            steps {
                script {
                    def pkgJson = readJSON file: 'package.json'
                    env.APP_VERSION = "v${pkgJson.version}"
                    echo "Building Version: ${env.APP_VERSION}"
                }
            }
        }

        stage('Package Desktop EXE & Publish Update') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            npx electron-builder --config electron-builder.json --publish always || npx electron-builder --config electron-builder.json --publish never
                        '''
                    } else {
                        bat '''
                            call npx electron-builder --config electron-builder.json --publish always
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
