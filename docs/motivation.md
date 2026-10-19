# Motivation, in Jamie's words

Source material for the report's Motivation and Impact sections. Jamie
was a founding member of the program this models, and coached in it.
Lightly cleaned from
speech; the claims and the framing are his, not reconstructed.

**This is evidence, not doctrine.** It is one practitioner's account, and the
report should credit it as exactly that.

---

## How the problem arrived: the club outgrew the conversation

It started with two coaches — Jamie and one other — running lessons and
clinics at one club.

> We were just there every day. Started off kind of small. We were doing
> lessons and clinics, but you kind of had a handle on everyone in the program
> and what they were working on. We had a good chat between the two of us —
> here's what this person's working on. So it was a lot more discussion.
> Smaller groups, so more personal.

The shared record existed. It was two people talking every day.

> Thankfully we were able to grow the business very quickly, scaled up pretty
> quick.

Three clubs now. And the thing that broke first was the thing nobody had
written down:

> As we scaled, just trying to keep touches on the ball and make sure — because
> it got more difficult to keep track of what people were working on. We're
> running the clinics and stuff, but you don't have a great sense of what
> everyone's working on individually.

**This is the actual origin of the product.** Not "coaches should take better
notes" — a conversation between two people that did not survive being a
conversation between eight.

## Why it is a squash problem specifically

> A lot of squash is just individual lessons. You might have a coach keeping
> track of things in a little notebook, and then the player will come in and
> they'll look at the notebook from last time.

The notebook works fine for one coach and one player. The program model breaks
it:

> The kind of program we're running is kind of unique in the squash world.
> We're not just a lesson factory where people come in and do lessons and then
> the occasional clinic. It's really clinic-based. So it's a very scalable
> business model, which is why we're at three clubs now.

> This is actually something that lets players and coaches both see what each
> other's thoughts were on the session, but also that broader sense of it being
> a bigger program where the coaches are interfacing with more than one kid at a
> time, and kids they don't give lessons to.

> That's why this kind of app doesn't really exist for squash — because there
> aren't many programs that are as big.

The last line is the novelty argument in one sentence: the tool is absent
because the organisational shape that needs it is rare. **"Coaches you don't
take lessons from still write about you"** is the specific thing no notebook
does, and it is why the visibility rules in `core/db.py` are the design, not
plumbing.

## Reflection: why the diary half exists

> Kids aren't reflecting and you're just doing the same thing over and over
> again. So kids will plateau, they won't get better.

> The ones who are actually able to reflect and keep building improve the
> fastest. It's more fun. And better for the kids.

From the earlier session, the two quotes that set this up:

> Every time, I'd ask "what did we work on last time?" and the kid would look
> back at me with a blank stare — "oh, I don't know." So you end up doing a lot
> of the same stuff, because it's tough to build when they don't have a
> recollection of what they worked on last week. You just have the same lesson
> over and over again.

> As much as I harped — hey, you need to be reflecting, you need to be writing
> this down — kids don't want to do that. They just want to show up and hit a
> ball. Which is fine. But that only gets you so far.

That second quote is the design constraint, and it is why the app is not a
journal with a streak counter. Reflection has to be cheap enough that a
fourteen-year-old does it in the thirty seconds they actually have — hence the
microphone, the one box, the private option.

## Four constituencies, one record

Jamie's own framing, which is a cleaner structure for the Impact section than
the one I had:

1. **The player.** They reflect, they see it written down, they are made to
   think about the session.
2. **The parent.** The growth complaint, in his words:
   > One of the criticisms we got was, as you start to grow, the coaches don't
   > have as much time for the kids, so they kind of lose the plot, lose the
   > thread a little bit with what's going on with their kids.

   > Everyone likes that feel of more personalized attention, especially
   > parents.

   This is why the read-only parent page is worth its screen: it is the answer
   to the specific thing customers said when the business scaled.
3. **The coaching organisation.** Coaches keep track of their lessons and can
   see what a colleague is working on with the same kid.
4. **Coach education and onboarding.** The one I had underweighted:
   > As you scale, you hire new coaches. I was onboarding coaches. It's not the
   > easiest thing to do when you have competing priorities. So just give them
   > a resource to look at instead of human-to-human talking.

   > One of those things of being a small business with a limited staff is it's
   > just not easy to educate people as quickly as you'd like. So having written
   > stuff is good.

   **This retroactively justifies the playbook and the methodology agent.** The
   cite-or-refuse resources screen is not a bolt-on feature; it is the
   onboarding problem, and it is the reason the playbook had to be a real
   document rather than a prompt.

> It's not only good for the business from a client perspective and making
> clients happy. It's good from a player perspective because they're
> reflecting. It's good from a coaching organization perspective.

## Next steps Jamie named

- **Wearables integration.**
- **Squash rating as an outcome measure** — tying the record to a number that
  moves, which is the closest this gets to measurable efficacy.
- **Building out the curriculum** — a fuller methodology, a drill bank. See the
  note below on why this is a decision rather than a gap.
- **Player logins**, with one admin who can see everything.
- **Hosting it somewhere**, so several coaches on different devices share one
  record.

Logins and hosting are the same next step: the moment it is on a public URL,
"I am: [dropdown]" stops being a demo convenience and becomes the whole access
control story.

---

## The theory note — keep it to what is defensible out loud

> You can bring in Ericsson's deliberate practice model. Actually, I don't know
> if reflection's on that.

Correct, and the useful version of this is short.

**Do not put scholarly hedging in the report that Jamie would have to defend in
a viva.** A first draft carried the failed 2019 replication of the Ericsson
violin study in a callout box. He read it and said, reasonably, that he did not
know what it meant. A citation the author cannot speak to is a liability, not
rigour. Cut.

**Ericsson, Krampe & Tesch-Römer (1993)** define deliberate practice by
well-defined tasks with specific goals, focused attention, immediate informative
feedback, and repetition with error correction. Self-monitoring appears in the
framework and in later summaries, but *reflection after the session* is not one
of its named components.

**Zimmerman's self-regulated learning cycle** is the one that names it:
forethought (goal setting, strategy choice) → performance (self-control,
self-observation) → **self-reflection** (self-judgement and self-reaction).
It has been applied directly to athletes, including think-aloud work with
academy goalkeepers and golfers reporting improved reflective skill and
self-monitoring.

So the framing for the report is:

> The club is already very good at deliberate practice. The drill ladder is
> structured tasks with specific goals; the coach standing on the court is
> immediate informative feedback; the conditioned game is repetition with error
> correction. What the program does not supply is the third phase of the
> self-regulation cycle. Nobody closes the loop, because closing it is
> homework and kids do not do homework. Rebound is an attempt to make the
> self-reflection phase cost thirty seconds.

That is a more defensible claim than "deliberate practice requires reflection",
and it maps onto what Jamie actually observed: the players who reflect improve
fastest, in a program where everyone gets the same quality of deliberate
practice.

**Hedge honestly.** Macnamara & Maitra (2019) re-ran the 1993 violin study and
did not replicate the core dose-response finding, and the sport self-regulation
evidence is thin — a 50-participant free-throw study, a two-goalkeeper pilot.
Cite these as a frame for the design, not as proof that the app works. The
report should say that plainly; overclaiming here is the easiest way to lose
credibility in the Impact section.

Sources:
- [Ericsson, Krampe & Tesch-Römer (1993), revisited](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6731745/)
- [Self-regulation in sports learning and performance](https://research.birmingham.ac.uk/en/publications/self-regulation-in-sports-learning-and-performance)
- ['Think Aloud' as a facilitator of self-regulation in golfers](https://researchonline.ljmu.ac.uk/17581/3/%E2%80%98Think%20Aloud%E2%80%99%20as%20a%20facilitator%20of%20self-regulation%20in%20golfers.pdf)
- [Think-aloud with academy goalkeepers](https://researchonline.ljmu.ac.uk/id/eprint/23252/1/McGreary%20et%20al%202024%20TA%20GK%20Manuscript%20Accepted%20version.pdf)

---

## The club, with dates

- **Planning from early 2021.** Doors open **January 2022** — mid-season, which
  was not the plan. COVID supply-chain delays pushed it. A small start as a
  result, then quick growth.
- **Plainsboro, New Jersey:** four coaches now, up from the original two.
- **Two further clubs**, in **Exton, Pennsylvania** and **Hartford, Connecticut**, both
  currently hiring. Neither has settled its methods, which is why the app
  models Plainsboro only.
- **Jamie was there from the 2021 planning stage until mid-2026** — five
  years, founding through last season — and left to come to business school.
  Write him as a current practitioner, not an alumnus looking back. Two drafts
  got this wrong: the first put it in the distant past, the second kept saying
  "three months ago", which draws attention to a departure that needs no
  explanation. The dates carry it.

Two coaches in 2022 who knew every player because they spoke every day, to
four at one club and two more clubs hiring, in under four years. **That is the
motivation in one sentence** — the record was a conversation, and the
conversation did not scale.

## Where the seed data comes from

Jamie kept three years of coaching notes. They are **not** a feature of the
app and there is no archive importer; they are the provenance of the sample
data, and the report should say that plainly:

> My three years of notes are what the sample players are based on. I just
> needed something to populate it. As this is built out it'll be the actual
> coaches and the actual players.

So: the six seeded players are **invented people carrying real patterns**. No
real child's record is in this repository. The cue vocabulary, the way the same
problems recur across months, the gap between what a coach writes and what a
player writes — those are drawn from the real notes. The names, and every
individual entry, are fabricated for the demo.

This needs saying in the report for two reasons. It is the honest answer to
"where did your data come from", and it is the reason the findings the agents
surface are plausible rather than arbitrary.

### The first-person "before"

The strongest version of the problem statement is that **the coach who cared
most about this still could not do it**:

> I didn't have anything super structured. For all my effort it became hard to
> keep track of things over time. I was just doing it in the Notes app on my
> phone.

A founding member of the academy, highly motivated, keeping notes in Apple
Notes — and still losing the thread. That rules out the lazy reading of the problem ("coaches
should just take better notes") and makes it structural, which is what
justifies building anything at all.

---

## Corrections and additions, second pass

Jamie read the first draft. What he changed:

- **He coached from 2022, not 2021.** Planning started early 2021; the doors
  opened January 2022; he coached from then until mid-2026.
- **Opened with fifteen kids.** Several hundred through the door over five
  years, across three clubs. Use these numbers rather than "it grew".
- **The competitive season is written down** — September to March, ending at
  Nationals, and it is already in playbook §7 with the full year table. An
  earlier draft listed "season phases are inferred" as a limitation. That was
  stale and wrong, carried over from an old blockers list. Removed.
- **"The notebook is genuinely better than software" overstated it.** His
  reading: it is simply what people do, and nothing has made them stop. Softened.
- **The food/weight exclusion does not need to be in the report.** It is a
  sensible product policy; it is not interesting enough to spend a bullet on
  in a Novelty section. Cut.
- **A clinic is up to thirty kids, not eight.**

### What the clinic floor actually looks like

This was missing and it is load-bearing:

> The coaches are standing outside the court. There's up to like 30 kids in a
> clinic. So they're just walking up and down the courts outside. Occasionally
> they'll step in and talk to someone. But that's why it's helpful to know
> what's going on with the players — so they can see who registered before and
> take a look at those players, just so they have a general sense.

The intervention is thirty seconds through glass, maybe twenty times an
evening. What makes it land is knowing what that child is working on *before*
you open your mouth. That is the product stated operationally, and it is a
better framing than anything abstract about records.

### The parent pressure has a number attached

> One summer we had 50 kids at a time on 7 courts with 3 coaches in the
> building. And I had to figure out how to run that. And parents would be like,
> I feel like my kid's not getting enough individualized attention. We got too
> popular for our own good.

This belongs in **Motivation**, not only in Impact. It is the commercial edge
of the same problem: the attention was there, and what had gone was the
program's ability to *show* it.

### He was a professional player

> I was also a professional player, and my notes were my notes as a player as
> well. So I had the coaching notes, also my playing notes. And again, I found
> it useful. I improved a lot more when I started reflecting. So I know the
> value of it, but still — tough to do in a structured way unless you're really
> judicious about it.

Worth including precisely because of the last clause. A professional, highly
motivated, found structured reflection hard. That is the strongest available
argument that a fourteen-year-old will not do it unaided.

### The feature idea worth building first

> We have a registry system. Maybe we can interlink those — you have 15 kids at
> a clinic, and you can hit summarize on those 15 that have registered, get a
> readout and see if there's a lot of commonalities. Maybe you want to alter
> the session based on what kids are working on.

**Summarize the room, not the player.** Everything built so far summarizes one
player; the coach outside the glass has a different question. Six kids stuck on
the same rung is not fifteen pieces of feedback, it is a different session plan.
This is the bleachers observation turned into a feature, and it is the first
thing to build after a pilot because it changes what a coach *does*, not just
what they know.

### A real accuracy limit

> The AI isn't perfect at figuring out whether things are routines or
> conditioned games. Long-long-short is a routine, for instance — three shots
> in sequence. Someone building out that playbook a bit more systematically
> over time might help it be a bit more accurate. But that's not a core
> feature.

Important and correctly scoped: this is a **documentation** gap, not a model
one. The drill taxonomy is underspecified in the playbook, the rung is what the
transfer-gap finding depends on, and the fix is a coach writing it out properly
with examples. No code.

### Not rotation — siloed lesson records

A draft said a player "sees a different coach most weeks". Wrong, and it
mis-states the problem:

> It's not that they're seeing a different coach. It's the same coaches, they
> just don't give lessons to them.

The staff is stable. The point is that **most of the coaches on the floor with
a given child do not give that child lessons** — they coach them in clinics two
evenings a week with no sight of what the lesson coach is working on. So this is
not an inconsistency-from-churn problem, which would be a weaker argument. It is
that the lesson record is siloed per coaching relationship while the clinic
floor is shared, and the notebook model assumes the person writing and the
person teaching are the same person.

### "Founding member", not "co-founder"

His own correction, and take it literally:

> Co-founder buys some equity I didn't have.

Use **founding member of the academy**, and lead with it rather than burying
it — it is the credential that makes section 1 worth reading. "Helped found"
and "helped start" also work. The distinction
is real — co-founder implies an ownership stake — and overstating a role in a
document with his name on it is a worse error than understating one. Nothing
about the argument depends on the bigger word: what makes the source credible
is five years on the floor, not a title.
