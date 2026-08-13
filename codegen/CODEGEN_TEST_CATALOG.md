# EmpMonitor Codegen Playwright Test Catalog & Execution Guide

This catalog documents the structured Playwright Codegen regression test suite for EmpMonitor.

---

## 📋 Test Matrix Catalog

| Script | Module | Functionality | Preconditions | Test Data | Assertions | Status |
|--------|--------|---------------|---------------|-----------|------------|--------|
| `auth/test_login.py` | Authentication | Valid login & navigation | Valid credentials | `EMPMONITOR_USERNAME`, `EMPMONITOR_PASSWORD` | URL changes, "Total Enrollments" visible | ✅ Active |
| `auth/test_invalid_login.py` | Authentication | Invalid login failure | None | Bad username & password | Username field remains visible | ✅ Active |
| `auth/test_logout.py` | Authentication | User logout | Authenticated context | None | Redirected to login page | ✅ Active |
| `auth/test_session_persistence.py` | Authentication | Session reload retention | Authenticated context | None | "Total Enrollments" visible after reload | ✅ Active |
| `dashboard/test_dashboard_overview.py` | Dashboard | Overview widgets & enrollment link | Authenticated context | None | Search box visible on enrollments click | ✅ Active |
| `dashboard/test_dashboard_filters.py` | Dashboard | Currently Active & Absent filters | Authenticated context | None | Filter popup / search box visible | ✅ Active |
| `employees/test_employee_list_search.py` | Employee Mgmt | Employee list search & table sorting | Authenticated context | Search term "suman" | Search text present in table | ✅ Active |
| `employees/test_employee_registration.py` | Employee Mgmt | Register new employee modal & submit | Authenticated context | Generated email/code | Form submit & OK confirmation modal | ✅ Active |
| `employees/test_employee_edit_details.py` | Employee Mgmt | Edit employee profile shift | Authenticated context | Shift selection | Update confirmation modal | ✅ Active |
| `monitoring/test_monitoring_control.py` | Monitoring | Tracking & DLP feature settings | Authenticated context | None | Group Settings & Save button visible | ✅ Active |
| `monitoring/test_agent_auto_update.py` | Monitoring | Agent auto update toggle | Authenticated context | None | Toggle button visible | ✅ Active |
| `monitoring/test_keystrokes_monitoring.py` | Monitoring | Key Strokes log view | Authenticated context | None | Application grid cell visible | ✅ Active |
| `productivity/test_productivity_rules.py` | Productivity | General settings rule visibility | Authenticated context | None | Settings tab visible | ✅ Active |
| `productivity/test_productivity_analytics.py` | Productivity | Top application analytics widget | Authenticated context | None | "Top Application Usage" header visible | ✅ Active |
| `applications/test_app_usage.py` | Applications | App history tracking list | Authenticated context | None | App usage header visible | ✅ Active |
| `websites/test_web_usage.py` | Websites | Web history list | Authenticated context | None | Web history tab visible | ✅ Active |
| `live_monitoring/test_live_monitoring.py` | Live Monitoring | Screen Cast connection controls | Authenticated context | None | Connect button enabled & clickable | ✅ Active |
| `screenshots/test_screenshot_view.py` | Screenshots | Screenshot date search | Authenticated context | Date filter | Search button enabled & clickable | ✅ Active |
| `screencast/test_screen_recording_list.py` | Screencast | Screen recording search | Authenticated context | None | "No screen records" empty state | ✅ Active |
| `attendance/test_timesheets.py` | Attendance | Timesheets grid & column sort | Authenticated context | None | Clock In/Out headers clickable | ✅ Active |
| `reports/test_report_generation.py` | Reports | Reports menu navigation | Authenticated context | None | Page URL updated | ✅ Active |
| `settings/test_localization_settings.py` | Settings | Localization settings save | Authenticated context | None | Save button visible and clickable | ✅ Active |
| `settings/test_storage_settings.py` | Settings | Storage type (S3 Bucket) options | Authenticated context | None | "Amazon - S3 Bucket" text visible | ✅ Active |
| `admin/test_roles_permissions.py` | Admin | Roles column header sort | Authenticated context | None | Role column header visible | ✅ Active |

---

## 🚀 How to Run the Tests

### 1. Required Environment Variables
Set the following environment variables before running the suite:

```bash
export EMPMONITOR_BASE_URL="https://app.dev.empmonitor.com/amember/member"
export EMPMONITOR_USERNAME="qt_dev"
export EMPMONITOR_PASSWORD="qt_developers"
```

### 2. Run the Entire Suite
To run all tests in the `codegen` directory using pytest:

```bash
pytest codegen/ -v
```

### 3. Run a Specific Module
```bash
pytest codegen/auth/ -v
pytest codegen/employees/ -v
pytest codegen/monitoring/ -v
```

### 4. Run an Individual Script
```bash
pytest codegen/auth/test_login.py -v
```

---

## 📊 Test Data & Golden Dataset Usage

- Credentials and system configuration thresholds are referenced from `/config/golden_dataset.json` and `/config/framework.json`.
- Dynamic test data (such as employee registration emails and employee codes) uses timestamped auto-generated strings to prevent duplicate key collisions.

---

## ⚠️ Known Limitations & Setup Requirements

1. **EmpMonitor Agent Requirement**:
   - Live stream screen casts, keystroke records, and live screenshots require an active, running EmpMonitor agent on a monitored Windows workstation.
2. **Screenshots & Video Captures**:
   - If no active agent is connected to the test account, screenshot and recording queries correctly assert the application's empty/unavailable state indicators (`"No screen records present for"`).
3. **Third-Party / External Integrations**:
   - Storage settings (Amazon S3 Bucket) are validated for UI state and configuration options without mutating third-party AWS production credentials.
