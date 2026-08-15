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
                            pip3 install playwright requests 2>/dev/null || pip install playwright requests 2>/dev/null || python3 -m pip install playwright requests 2>/dev/null || echo "Python pip dependencies checked."
                        '''
                    } else {
                        bat '''
                            if exist package-lock.json del /f /q package-lock.json
                            call npm install --force
                            call npm install --no-save @tailwindcss/oxide-win32-x64-msvc @rollup/rollup-win32-x64-msvc lightningcss-win32-x64-msvc @esbuild/win32-x64
                            python -m pip install playwright requests 2>nul || py -m pip install playwright requests 2>nul || pip install playwright requests 2>nul || echo "Python pip optional step skipped on build agent."
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
                    if (isUnix()) {
                        env.APP_VERSION = "v" + sh(script: "node -p \"require('./package.json').version\"", returnStdout: true).trim()
                    } else {
                        env.APP_VERSION = "v" + bat(script: "@node -p \"require('./package.json').version\"", returnStdout: true).trim()
                    }
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
