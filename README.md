# Rebound

A shared training diary for Squash Tigers Academy, a junior squash club — and
four agents that read it.

Players reflect on a session in a sentence. Coaches write up a lesson in their
own language. The app files both against the club's curriculum, and reads the
record back: what a player is working on, which cue has stopped transferring
between drill types, and which problem has been coming back for three months.

Final project for MGT 409 *AI Foundations*, Yale School of Management.
Runs on `gpt-6-luna` through a Portkey gateway.

---

## Running it

Needs **Python 3.11 or newer** (built and tested on 3.14).

```bash
git clone <this repo>
cd rebound
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python app.py
```

Then open **http://127.0.0.1:8050**.

The database creates and seeds itself on first run — six players, three
coaches, 472 entries across a twelve-week block. Nothing to migrate, no
fixtures to load.

### The .env

The app looks for `.env` in this folder first, then in **every parent folder**,
and uses the nearest one. So either location works:

```
submissions/
├── .env            ← here (the grading layout)
└── rebound/
    ├── .env        ← or here
    └── app.py
```

One variable is required. Copy `.env.example` and fill it in:

```
PORTKEY_API_KEY=your-portkey-key-here
```

`MODEL_NAME` and `PORTKEY_BASE_URL` are optional and already correct by default
— you should not need to set either.

Without a key the app still starts and every screen renders against the seeded
data; only the buttons that call the model will fail, and they say so.

---

## What to click first

Start as **Maya Okonkwo**, the player selected by default. The "I am" dropdown
at the top switches between every player, coach, parent and the admin — there
is no login, deliberately (see the report's Limits section).

**1. See the problem the app is for.** As Maya, go to **My lessons** and press
**Summarize**. About twenty seconds. It reads her fifteen lessons end to end
and reports, among other things, that in August she wrote she was bored of
hearing about her racket and *no later lesson ever answered her*. That finding
is the clearest thing in the project.

**2. See it from the other side.** Switch to **Nia Carter** (coach) → **Players**
→ **Maya Okonkwo** → **Review**. The Comparison agent reports the transfer gap
— her racket preparation holds in slow work and disappears in a game — and the
same cue recurring across three consecutive Drop Weeks, which is twelve weeks
unresolved.

**3. Write something.** As Nia, **My lessons** → type a name in the search →
pick a player → write a note in your own words. The Organizer files it and
drafts the version the player will read. **It is not sent until you approve
it**, which is the one rule in the app worth knowing about.

**4. Watch the privacy boundary hold.** As Maya, write a reflection and press
**Keep private** instead of Save. Switch to any coach and look at her record:
the entry is not there, and nothing indicates one exists. That exclusion is a
`WHERE` clause in `core/db.py`, not an instruction in a prompt.

**5. See what it cost.** **Usage** shows the real token ledger — every call the
app has made, what cached, and what it came to. Nothing calls the model off the
books.

Also worth a look: **Coach resources** (ask a method question, get an answer
with playbook citations, or a refusal if it cannot cite) and the **parent**
accounts, which are read-only and see less than a coach does.

The date control in the top bar moves a simulated "today" forward and back a
week at a time, so a twelve-week curriculum loop can be walked through in a
couple of minutes.

---

## Tests

Two suites are **free** and run in about a second:

```bash
./venv/bin/python scripts/check_db.py        # 42 checks: schema, visibility, the privacy rules
./venv/bin/python scripts/check_screens.py   # 61 checks: every screen renders for every role
```

Five suites **call the live model and cost money** (a few cents each):

```bash
./venv/bin/python scripts/check_model.py         # the Portkey connection works
./venv/bin/python scripts/check_organizer.py     # entries get filed correctly
./venv/bin/python scripts/check_comparison.py    # transfer gaps and chronic cues
./venv/bin/python scripts/check_methodology.py   # cite-or-refuse, and citations are real
./venv/bin/python scripts/check_injection.py     # prompt injection and suppression attacks
```

And a report, free, reading the ledger already on disk:

```bash
./venv/bin/python scripts/tokenomics.py
```

---

## Layout

```
app.py                   Dash app — the shell, the clock, player screens, usage
coach_views.py           coach, parent and shared views
core/config.py           Portkey client, model name, the .env parent walk
core/db.py               SQLite. The visibility boundary lives here, in SQL
core/metering.py         token + cost ledger. Nothing calls the model off the books
core/analysis.py         counting, done in Python so the model cannot argue with it
core/agents/             organizer, comparison, recap, methodology
data/playbook.md         ~6,900 words. The club curriculum, cited by the agents
data/seed.py             six players, each seeded to make one finding discoverable
scripts/check_*.py       PASS/FAIL harness
report.html              the write-up
slides.html              the deck
```

## Notes

- To start over, delete `data/rebound.db` and run `app.py` again.
- The app runs with Dash's reloader off, so editing a file will not restart it.
  Stop it with Ctrl-C and start it again.
- All player data in this repository is **synthetic**. The six seeded players
  are invented people carrying patterns drawn from three years of real coaching
  notes. No real child's record is here.
