# understand.md — the whole story, explained simply (my private notes)

This is just for me. It explains, in very plain words, what this project is and
everything we did. No fancy words without explaining them first.

---

## 1. Why am I even doing this?

A company called **Agivant** is thinking about hiring me. Before they hire, they
gave me a **practice task** (like a test) to see if I'm good at this kind of work.
The work is "QA" — **Quality Assurance** — which just means: *try to break a
thing on purpose, and carefully write down how it behaves when it breaks.*

So this whole project is my answer to their test task.

---

## 2. A few simple ideas first

Think of these like toys:

- **A database** = a giant, smart notebook that stores information and can answer
  questions about it really fast. ("Who are Tom's friends?" → it answers instantly.)
- **TigerGraph** = the *brand* of smart notebook we're testing. It's special
  because it's great at storing **connections** — like a web of friends (Tom knows
  Sara, Sara knows Raj…). That kind of database is called a **graph database**.
- **A node** = one computer doing part of the work. Big systems use **several
  computers as a team** so they can handle a lot and not get tired.
- **High Availability (HA)** = the system is built so it **keeps working even if
  one computer breaks.** 

  Imagine you and 2 friends each keep a copy of the class homework. If one friend
  is absent, the homework isn't lost — the other two still have it. That backup
  idea is exactly what "High Availability" means for a database.

- **Node failure** = a computer in the team suddenly stops (it crashed, lost
  internet, or got switched off). The big question: *does the database keep working
  when that happens, and how fast does it heal?*

---

## 3. What the task actually asked me to do

In simple words, three things:

1. **Set up TigerGraph with the "backup copies" (HA) feature turned on**, using a
   team of computers.
2. **Break the computers on purpose** (turn them off, freeze them, cut their
   internet) and watch what happens.
3. **Write a report** that answers: What did I test? Why did I pick those tests?
   What worked, what didn't? When it broke, how long was it down, and how long
   until it healed? (That "time to heal" has a name: **MTTR** — basically
   *"minutes/seconds to recover."*)

---

## 4. The tricky problem (important!)

To turn on the "backup copies" (HA) feature, TigerGraph needs a **special paid
permission slip** — a **license**. 

The free license I could get does **not** include the HA permission. It literally
says "HA: not allowed." So right now the database can only run in **single-copy
mode** (no backups) — *not* the full HA mode the task wants.

This is the **one big thing still missing.** Everything is built and ready; the day
I get the proper HA license, the exact same tests will run the full HA version with
no extra work.

(Two smaller side-notes, also private: the download site only had version **4.1.4**,
not the **4.1.3** the task named — they're basically the same family, so I used
4.1.4. And early on a senior suggested a "cloud" version of TigerGraph called
**Savanna**, but that one doesn't let you switch computers off, so it was useless
for a *break-the-computers* test — I used the do-it-myself version instead.)

---

## 5. What we actually built

Because I don't have 3 real computers lying around, I used **"pretend computers"**
on my laptop called **containers** (think: 3 separate sealed lunchboxes, each
running its own mini-computer). I named them **tg1, tg2, tg3**. Together they form
the TigerGraph team.

Then I built a little **robot tester** (written in a language called Python) that
does this on its own:

1. Keeps **poking** the database 4 times every second, asking a simple question,
   and writing down "did it answer? yes/no" with the exact time.
2. **Breaks** one of the pretend computers (turns it off, freezes it, or cuts its
   network).
3. Watches how long the database struggles.
4. **Fixes** the broken computer and waits until everything answers normally again.
5. Does the math: *how fast did it notice the break? how long was it down? how long
   to fully heal?*

I also put in some **practice data** — 5,000 pretend people and 15,000 pretend
friendships — so the database has real work to do while I'm breaking things.

These automated tests are written with a popular testing tool called **pytest**, so
anyone can re-run them with one command and see them pass.

---

## 6. The bumps we hit along the way (and fixed)

- My **first version of the tester was written in a different language (bash)** and
  it kept **crashing in the middle**. After digging in, the real reason wasn't my
  code — my **laptop was running out of memory**. Too much was crammed in at once.
- So I **rewrote the tester in Python** (much sturdier on Windows) **and freed up
  memory** by telling the system to use less. After that, everything ran smoothly.
- Once it ran fully, the live run **caught two small mistakes in my own math**,
  which I fixed (how I measured "fully healed," and how I checked that no saved data
  was lost). Good — that's the testing doing its job.

End result: **all 8 automated tests pass.**

---

## 7. What we found (the results, in plain words)

I broke the system in 6 different ways and measured how long it took to heal:

| What I broke | How long it was down / healed |
|---|---|
| Turned a computer off suddenly | ~52 seconds to fully heal |
| Shut a computer down politely | ~53 seconds |
| Froze a computer (still on, not answering) | ~23 seconds (fastest) |
| Cut a computer's network (isolated it) | ~33 seconds |
| Broke just one *part* of a computer | noticed after ~11 sec, healed ~57 sec |
| Turned off the **main** computer | ~56 seconds (and it still survived!) |
| Tried to **save new data while broken** | nothing already-saved was ever lost |

**The big lessons, simply:**

- How long it takes to heal depends mostly on **how** it heals: if a computer has
  to fully restart, ~52–57 seconds; if it just unfreezes or reconnects, ~23–33
  seconds.
- A whole computer dying is felt **instantly**; one small broken part is tolerated
  for ~11 seconds before anyone notices.
- **No saved information was ever lost.** (Though when the network was cut, a few
  "save" requests *looked* like they failed but actually went through — worth
  knowing.)

⚠️ Remember: these results are from **single-copy mode** (no HA yet). They show how
the system behaves *without* backups — which is exactly why HA matters. With the HA
license, we'd expect the system to barely hiccup instead of going down for ~50
seconds.

---

## 8. Where things stand right now

- The 3-computer team is built, and all my automated tests **pass**. ✅
- The report is written and tidy, ready to show. ✅
- The only thing missing for full marks: the **HA license** (then the same tests
  run the "with backups" version automatically). ⏳
- I shut Docker down afterward to give my laptop its memory back.

**To turn it back on later:** start Docker → bring the 3 computers up → start
TigerGraph → run the tests. (The exact commands are in the README.)

---

## 9. What's left to do (my to-do list)

1. **Save my work** to GitHub (one "commit + push" command — already prepared).
2. **Get the HA license** → re-run the install → the tests run the full HA version.
   This is the one real gap.
3. **Send it in** — share the GitHub link (and report) the way the recruiter asked.

---

## 10. My score, honestly

**About 68 out of 100.**

- The testing tool, the measurements, and the report are **really solid** (that
  part is basically an A).
- BUT the heart of the task was testing the **backup (HA)** feature, and I couldn't
  actually turn HA on (no license yet). So I tested the "no-backup" version
  thoroughly instead.
- The moment I get the HA license, the same work jumps to **~90+**, because then
  I'm testing the exact thing they asked for.

In one sentence: **I built the whole testing machine and proved it works; the only
missing piece is the paid HA key that lets me test the backup feature itself.**
