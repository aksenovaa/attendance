CREATE TABLE IF NOT EXISTS employees(
  employee_id INTEGER PRIMARY KEY, tab_number TEXT, pin_code TEXT, full_name TEXT,
  department_id INTEGER, position_title TEXT, schedule_id INTEGER,
  start_date TEXT, end_date TEXT, shop TEXT, exclude_from_timesheet INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS departments(
  department_id INTEGER PRIMARY KEY, title TEXT, pid INTEGER);
CREATE TABLE IF NOT EXISTS locations(
  location_id INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE IF NOT EXISTS schedules(
  schedule_id INTEGER PRIMARY KEY, title TEXT, type INTEGER);
CREATE TABLE IF NOT EXISTS events_raw(
  event_key TEXT PRIMARY KEY, employee_id INTEGER, event_full_date TEXT,
  event_code INTEGER, mode TEXT, location_id INTEGER, serial_number TEXT,
  source TEXT, pulled_at TEXT, run_id TEXT);
CREATE TABLE IF NOT EXISTS day_frame(
  employee_id INTEGER, day TEXT, is_work_day INTEGER, is_holiday INTEGER,
  work_time TEXT, absence_title TEXT, source TEXT, run_id TEXT,
  PRIMARY KEY(employee_id, day));
CREATE TABLE IF NOT EXISTS corrections(
  id INTEGER PRIMARY KEY, month TEXT, employee_id INTEGER, day INTEGER,
  action TEXT, cin TEXT, cout TEXT, worked TEXT, source TEXT,
  confidence TEXT, note TEXT, accepted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS shifts_final(
  employee_id INTEGER, day TEXT, cin TEXT, cout TEXT, worked TEXT,
  tag TEXT, source TEXT, rule TEXT, run_id TEXT, PRIMARY KEY(employee_id, day));
CREATE TABLE IF NOT EXISTS audit(
  run_id TEXT, employee_id INTEGER, day TEXT, field TEXT,
  old_value TEXT, new_value TEXT, rule TEXT, source TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, month TEXT, started_at TEXT, finished_at TEXT,
  git_commit TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS writeback_ledger(
  event_key TEXT PRIMARY KEY, employee_id INTEGER, event_time TEXT,
  event_code INTEGER, kind TEXT, posted_at TEXT, response TEXT);
CREATE INDEX IF NOT EXISTS ix_events_emp_date ON events_raw(employee_id, event_full_date);
