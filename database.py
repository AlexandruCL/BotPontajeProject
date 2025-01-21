import sqlite3

def init_db():
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clock_times (
                 user_id INTEGER,
                 date TEXT,
                 clock_in TEXT,
                 clock_out TEXT)''')
    conn.commit()
    conn.close()

def add_clock_in(user_id, date, clock_in):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("INSERT INTO clock_times (user_id, date, clock_in, clock_out) VALUES (?, ?, ?, ?)",
              (user_id, date, clock_in, None))
    conn.commit()
    conn.close()

def update_clock_out(user_id, date, clock_out):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("UPDATE clock_times SET clock_out = ? WHERE user_id = ? AND date = ? AND clock_out IS NULL",
              (clock_out, user_id, date))
    conn.commit()
    conn.close()

def get_clock_times(user_id, date):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("SELECT clock_in, clock_out FROM clock_times WHERE user_id = ? AND date = ?", (user_id, date))
    rows = c.fetchall()
    conn.close()
    return rows

def get_ongoing_sessions(user_id=None):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    if user_id:
        c.execute("SELECT user_id, date, clock_in FROM clock_times WHERE user_id = ? AND clock_out IS NULL", (user_id,))
    else:
        c.execute("SELECT user_id, date, clock_in FROM clock_times WHERE clock_out IS NULL")
    rows = c.fetchall()
    conn.close()
    return rows

def remove_session(user_id, date, clock_in):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("DELETE FROM clock_times WHERE user_id = ? AND date = ? AND clock_in = ?", (user_id, date, clock_in))
    conn.commit()
    conn.close()