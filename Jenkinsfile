pipeline {
    agent any

    environment {
        // GitHub Token credential configured in Jenkins Credentials Manager
        GH_TOKEN = credentials('github-release-token')
        GITHUB_TOKEN = credentials('github-release-token')
    }

    stages {
        stage('Checkout & Git Metadata') {
            steps {
                checkout scm
                script {
                    if (isUnix()) {
                        env.GIT_COMMIT_HASH = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                        env.GIT_COMMIT_MSG = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                        env.GIT_AUTHOR = sh(script: 'git log -1 --pretty="%an <%ae>"', returnStdout: true).trim()
                        env.GIT_BRANCH_NAME = sh(script: 'git rev-parse --abbrev-ref HEAD', returnStdout: true).trim()
                    } else {
                        env.GIT_COMMIT_HASH = bat(script: '@echo off\nfor /f "tokens=*" %%i in (\'git rev-parse --short HEAD\') do echo %%i', returnStdout: true).trim()
                        env.GIT_COMMIT_MSG = bat(script: '@echo off\nfor /f "tokens=*" %%i in (\'git log -1 --pretty=%%B\') do echo %%i', returnStdout: true).trim()
                        env.GIT_AUTHOR = bat(script: '@echo off\nfor /f "tokens=*" %%i in (\'git log -1 --pretty="%%an <%%ae>"\') do echo %%i', returnStdout: true).trim()
                        env.GIT_BRANCH_NAME = bat(script: '@echo off\nfor /f "tokens=*" %%i in (\'git rev-parse --abbrev-ref HEAD\') do echo %%i', returnStdout: true).trim()
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
                        env.APP_VERSION = "v" + versionMatch[0][1]
                    } else {
                        env.APP_VERSION = "v1.0.0"
                    }
                    echo "Target Release Version: ${env.APP_VERSION}"
                    
                    // Set Jenkins Build Display and Description with Git Commit Message
                    currentBuild.displayName = "#${BUILD_NUMBER} - ${env.APP_VERSION}"
                    currentBuild.description = "Commit [${env.GIT_COMMIT_HASH}]: ${env.GIT_COMMIT_MSG}"
                }
            }
        }

        stage('Package Desktop EXE & Publish Update') {
            steps {
                script {
                    echo "Publishing release artifacts to GitHub for Auto-Updater feed..."
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
            echo "Successfully built and published EmpMonitor Desktop Suite ${env.APP_VERSION} for commit '${env.GIT_COMMIT_MSG}'"
        }
        failure {
            echo "Jenkins build failed. Check console output for diagnostic details."
        }
    }
}
