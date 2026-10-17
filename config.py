"""Central configuration for the Suwar system.

Database settings can be changed here or overridden with environment
variables (SUWAR_DB_HOST, SUWAR_DB_USER, SUWAR_DB_PASSWORD, ...).
"""
import os

# ---- MySQL connection -------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("SUWAR_DB_HOST", "localhost"),
    "port": int(os.environ.get("SUWAR_DB_PORT", "3306")),
    "user": os.environ.get("SUWAR_DB_USER", "root"),
    "password": os.environ.get("SUWAR_DB_PASSWORD", "MKS2294"),   # <-- put your MySQL password here
    "database": os.environ.get("SUWAR_DB_NAME", "suwar"),
}

# ---- Business rules (from the project design) -------------------------------
LEAK_THRESHOLD = 8.0          # L/s: flow above this is a leak
HIGH_FLOW_THRESHOLD = 7.0     # L/s: flow above this limits reservations
MAX_ALERTS_PER_HOUR = 3       # per sensor
MAX_SLOTS_HIGH_FLOW = 1       # slots per farmer when flow is high
MAX_SLOTS_NORMAL = 2          # slots per farmer otherwise

# ---- UI ---------------------------------------------------------------------
REFRESH_SECONDS = 5           # how often sensors are read and the screen refreshed

# ---- Roles / access control (User.accessLevel in the class diagram) ----------
ACCESS_FARMER = 1
ACCESS_STAFF = 2          # technician, engineer
ACCESS_SUPERVISOR = 3
ACCESS_DIRECTOR = 4
ACCESS_ADMIN = 5
ROLE_LEVELS = {"farmer": 1, "technician": 2, "engineer": 2,
               "supervisor": 3, "director": 4, "admin": 5}

# ---- Security (DataSecurity) --------------------------------------------------
# Secret used to derive the encryption key for stored reports. Change it before real use.
ENCRYPTION_SECRET = os.environ.get("SUWAR_SECRET", "suwar-demo-secret-change-me")
PBKDF2_ITERATIONS = 100_000
DEFAULT_PASSWORD = "suwar123"      # password given to the sample accounts
MIN_PASSWORD_LENGTH = 6
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

# ---- Gates and schedule ---------------------------------------------------------
MAX_GATE_FLOW = 15.0              # L/s
DEFAULT_GATE_FLOW = 5.0           # L/s used when a closed gate is opened
SCHEDULE_START = "06:00"          # ScheduleManager.startTime
SCHEDULE_END = "19:00"            # ScheduleManager.endTime
SLOT_DURATION_MINUTES = 60
