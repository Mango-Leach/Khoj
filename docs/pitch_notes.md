# Pitch notes: what is real, simulated and roadmap

Keep this honest. Update it at the end of every milestone. Pitch only what is listed under "Real".

## Real (built and tested)

- Mobile OTP login, student and teacher profiles, guardian consent for under 18, sign-in by mobile number and code only, with Sign out for shared phones (M1). There is no PIN and no lock screen; each person on a shared phone signs in with their own number.
- Voice intake in Hindi and Marathi through Gnani speech, with confirm-back, typed fallback and no stored audio (M2).
- The public landing page reads its opening aloud in the same server voice as the app (browser voice if the server voice is off). Lines already spoken are served from the cache; new lines for visitors are limited per address and across all visitors, so it cannot burn the speech credits. The people drawn on the page are illustrations, and the page says so.
- Skills are kept only when the learner's own words support them. Ticked picture tiles show interest and never create a skill (M2).
- Career paths (M3): 15 careers across 8 families, 7 in full depth. A learner sees their 3 best-fit paths first, then up to 3 more that are somewhat related; careers with no real link to what they said are hidden, and a learner with nothing to go on gets 3 labelled starting points. Ranked by plain scoring code
  (skill match 0.40, local demand 0.25, first-income speed 0.20, feasibility 0.15). Each path has a reason, a five-step ladder,
  a first-income step and cited sources. Choosing a path creates the learner's journey.
- Paths are shown to everyone whatever their age. Under 18, electrical, motor, pump and solar paths carry a plain safety note:
  theory and a training board only, no live-circuit work until 18.

- Scholarships and schemes (M4): 8 schemes checked by a plain-code rules engine, never by a model. Each result is Eligible, Not eligible
  (with the failed condition named) or Check with the office. A learner's age, class and state come from their saved profile; the few
  extra answers (income, group, school type) are used for that one check and are not stored. A learner under a scheme's minimum age
  sees "this opens when you are 18" instead of a refusal.
- The engine never guesses: a missing answer, a rule value still marked `TODO_VERIFY`, a past end date, or a record nobody has checked
  for 90 days all give "Check with the office".

- Learning material: each career page has a "Where to learn" section of real courses linked out from official sites (SWAYAM, NPTEL,
  NIOS, NSDC, the Telecom Sector Skill Council). 19 links across the 7 full-depth careers; school-level options come first for a
  school learner and courses in the learner's language first. Nothing is copied or hosted.

- Teachers and mentor matching (M5): a teacher reaches tier 1 only after two checks, their proof photos being checked (a certificate, a
  work sample, experience or a reference) and a passed practical test (five sample descriptions of learners' work scored 1 to 4; 4 of 5
  within one point of an expert's score; 3 tries). A learner then sees up to 3 mentors, chosen by plain scoring code (skill 0.35,
  language 0.20, free places 0.15, trust 0.20, nearness 0.10) after hard filters (tier 1 or more, a verified skill the path needs,
  a free place). A request holds one place straight away, the mentor has 48 hours to accept or decline, and a lapsed or declined
  request lets the learner choose again without being offered the same mentor.
- Phone numbers never leave the server: a mentor sees a learner's name, class, block, language and the skills they told us about, and a
  learner under 18 on an electrical or motor path is flagged so the mentor teaches theory and a training board only.

- A mentor is optional. Courses and learning links are open from the moment a learner picks a path, with or without a mentor, and a
  mentor can be asked for at any later time without losing progress. The Home card leads with "Start learning" and offers "Find a
  mentor (optional)". Anything a mentor must do (review work, approve milestones, be paid per milestone) still needs a mentor.

- **Assignments and mentor review (M6).** A learner's path has three milestones: Explore, Learn, Practise (the first three rungs of the
  five-rung ladder; Certify and Earn happen outside the app). Each starts with one default assignment built from the career card, in
  English, Hindi and Marathi, so a learner can practise at once with no mentor. They write an answer (typed or spoken) and add up to 3
  photos, and the work stays saved. Sending it to a mentor needs a mentor. A mentor can ask the AI for up to 3 more assignments per
  milestone, edit them and approve them; a draft is invisible to the learner until a person approves it. The AI drafts nothing about
  money, and on an electrical or motor path any draft that tells a learner to switch on, energise or touch live work is dropped.
- **The review is people and plain rules.** The mentor gives every criterion its own score from 1 to 4 (there is no approve-all).
  Code decides: approving needs every score at 2 or more, otherwise the work can only be returned with feedback. After a second return
  the mentor is asked to call the learner. The optional "ask the AI" suggestion sees only the written answer (never the photos),
  never offers itself on a random one in ten (an audit sample), and is only a suggestion. The learner confirms yes or no that they
  received the feedback; a payout will wait for that (M7). Approving a photo is never described as certifying the work is safe.
- **How it differs from the source spec (flag to the team):** the spec has one multipart `POST /assignments/{id}/submissions`. It is split
  into save (JSON), photos, and send, so a weak connection can resume and a retry makes no duplicate. The spec says "3 to 5
  assignments per milestone"; the build starts with 1 default per milestone and lets the mentor add up to 5 more.
- **Not built in M6:** the spec's separate `/feedback/:id` page (feedback is on the assignment page), translating the mentor's
  feedback into the learner's language (the mentor writes it in whichever language they choose), a queue that holds saved work while
  offline (the connection badge appears but nothing is queued yet), notifications for "review ready" (M8), the payout flags for fast
  or identical approvals (M7; the time a review was open is already recorded), and the practical-work photo checks (M9; photos get
  only the blur, brightness and size checks).

- **Finishing a path, opportunities, the job pack and the inbox (M8).** When a mentor has approved every step, the learner taps "Finish
  my path" and it opens to opportunities. 13 real programmes and portals are seeded, each linked out with a source, an "entered on"
  date and an "Awaiting verification" label: apprenticeships (NAPS, NATS), skill training (PMKVY, RSETI, DDU-GKY, KVK, Suryamitra), PM
  Vishwakarma, the CSC village entrepreneur, Maharashtra's paid youth internship and jobs portal, MPSC and Maharashtra Police. The top 3 are
  ranked by plain code with the spec's starting weights (0.40 fit with the path, 0.25 how near, 0.20 whether it pays, 0.15 source
  trust and recency). Eligibility is the same rules engine as the schemes: a hard filter drops a deadline that has passed and a rule
  the learner definitely fails (shown under "Not open to you yet", with when it opens), and anything with an unconfirmed value says
  "Check with the office". Nothing is called eligible while a needed value is a placeholder. KHOJ never applies for anyone: a learner
  says "interested", the mentor may mark that they helped, the learner says "I applied" and later "I got a place". Only the learner can
  confirm, and a mentor has no call that sets applied or confirmed. A high-risk trade shows that a qualified assessor must check the
  work in person; KHOJ does not certify anyone.
- **Opportunities unlock as a mentor approves work.** A learner with a chosen path sees 2 previews straight away. One mentor-approved
  step shows 3, two show up to 6, and finishing the path shows everything, including "Not open to you yet". Only a mentor's approval
  counts, so practising alone does not unlock more. The server holds the rest back: a hidden programme is never sent, not even its name,
  and the learner is only told how many are waiting. "I am interested" works on any visible programme and reaches the mentor, who can
  help while the learner is still on the path. The job pack stays locked until the path is finished. The seeded list is short (at most
  about 5 per path), so the 6-step level only shows once more programmes are added.
- **A day in the life: career calls.** A mentor whose skill check and proof are approved (tier 1 or above) can switch on "offer career calls" and post 30 or 45 minute times, between 7 am and 9 pm Indian time. Any learner on that path can book one, with no mentor needed. KHOJ only handles the booking: the call happens on the mentor's own video link or phone number outside the app, and nothing is recorded or streamed. The label says "Skill verified in ...", never that the mentor works in the job, because the skill check proves skill, not employment. A learner under 18 confirms a guardian or facilitator will be nearby, and everyone ticks a short code of conduct. The contact is shown only to the mentor and the learner who booked; the mentor sees a first name only. One call at a time per learner. After the call the learner records whether it happened and rates it. It is unpaid and never touches the ledger. Real in the demo; the Hindi and Marathi wording is a draft for native review.
- **Connect (adult learners with similar goals).** Learners aged 18 and over can switch on a card and find others on the same path or with a skill in common. The card shows a first name, the state, the path and skills from the controlled list: no surname, photo, district, school, free text or contact. It is off until the learner turns it on and ticks that KHOJ cannot see or protect what happens outside the app. Suggestions only: there is no search by name and no list of everyone. One person asks, the other accepts, and only then do the two see each other's contact, which each typed in for this purpose (a phone or WhatsApp number, or an https link). Then they talk however they like outside KHOJ. There is no chat in the app. A learner can decline, remove a connection, block or report (a report also blocks), at most 5 requests a day, and a declined person cannot be asked again. Learners under 18 see only a note that connecting opens at 18. Honest limits: the age is what the learner entered, so this is not proof of age; reports are stored but there is no review screen yet, so we promise nothing about an answer; and the demo has no other real learners, so the suggestions stay empty until real accounts switch their cards on. A data-protection check with counsel is needed before a pilot. The Hindi and Marathi wording is a draft for native review.
- **Honest limits of the opportunity data.** The official pages for DDU-GKY, the RSETI age range, the KVK courses, MPSC and Maharashtra
  Police could not be read, so their rules are `TODO_VERIFY` and those records always say "Check with the office". CSC, Suryamitra and the
  Maharashtra internship were read from the official site. No pay or loan amount is stored or shown. Hindi and Marathi text is a
  machine draft and is labelled as such. Local businesses posting their own openings (first-party) is not built, so a path with
  no seeded programme shows the two general ones (the Maharashtra portal and the youth internship).
- **The job pack** is built only from cited data: the papers the linked programmes name, how to apply to each (with its source),
  practice questions for a first conversation, and the path's courses. Local employers, pay notes and workers' rights are left out
  because there is no sourced data for them yet, and the page says so.
- **The inbox** stores a kind and a few plain values, never finished text or a name, so the sentence is made in the reader's language and
  stays neutral on a shared phone. It covers: mentor request, accepted or declined, new work to review, review ready, path finished,
  wants help applying, mentor helped. Not built: web push (so the quiet-hours and two-a-day rules have nothing to apply to yet),
  assignment-due and scheme-deadline reminders (no due dates or deadlines are stored), the 14-day no-activity nudge (needs a
  scheduler), and "payout released" (M7).
- **Not built in M8:** the spec's "spot-check clear" before completion (it needs the tier 2 audit from M7, so finishing currently needs
  only the mentor's approvals), and a provider confirming an enrolment (only the learner confirms for now).

- **AI review for learners with no mentor.** Without a mentor, sent practice work is reviewed by an AI model straight away and labelled "Reviewed by AI". It reads the written answer only, gives scores and short feedback, and never passes high-risk work such as wiring. It is practice feedback: it does not finish a milestone, unlock opportunities or pay anyone. A person (a mentor) is still what approves real progress. Say "AI feedback", never "AI approval". Real in the demo; the Hindi and Marathi wording is a draft for native review.

## Simulated or seeded (say so)

- OTP is a fixed code. With `DEMO_ALLOW_ANY_NUMBER=true` any mobile number can sign in with it (no SMS gateway is built), so say plainly
  that sign-in is simulated and is not real authentication: anyone who knows a number and the code can sign in as it. While that switch
  is on, nobody can become admin by phone number.
- Local demand per district is a team judgement used only to nudge the order of paths. It is never shown to a learner as a fact or a number.
- No rupee figures are shown anywhere. Income ranges will appear only where a cited source and date exist.

## Awaiting a human

- Every career source reads "Awaiting verification" until a person sets `verified_on`. No machine sets that date.
- Hindi and Marathi text is draft. Static UI strings and the career reason templates need a native speaker.
  The five-step ladders in Hindi and Marathi are machine-translated (Gemini) and labelled as such on screen.
- Reason sentences may be rewritten by a local model. They are accepted only if short, plain and free of numbers, money or demand claims.
  Otherwise the template sentence stays.

- **Scheme rules (8).** Entered on 2026-11-19 from official pages, all showing "Awaiting verification" until a person sets `verified_on`.
  Read in full from the official page: the Maharashtra Post-Matric Scholarship for SC students, the Maharashtra Rajarshi Shahu Maharaj
  fee concession, and NATS. Not opened in full (the official sites refused automated access), so the values come from official text
  quoted in search results and must be checked against the document by a person: NMMSS, PM YASASVI, PM Vishwakarma, PMKVY, NAPS.
  The `research_note` in each file in `backend/data/schemes/` says exactly what was and was not read.
- **Values still `TODO_VERIFY`** (so these schemes can never show Eligible yet): NMMSS (class a new award is open to; qualifying marks, which
  the guidelines give for Class VII in one place and VIII in another), PM YASASVI (qualifying marks, 60% in one source and 33% in others),
  PMKVY (end date after FY 2025-26; entry rules per job role), NAPS (end date; education rules per trade), NATS (field of study: the
  portal's two pages disagree).
- **Course links (19).** Found on 2026-11-19 as page titles and URLs from each provider's own site, and every address answered when
  checked with `scripts/check_resources.py`. SWAYAM, NPTEL and Skill India build their pages in the browser, so I could not read dates,
  fees or languages from them: those are recorded only where a listing stated them (for example the NIOS poultry course is in Hindi,
  the IGNOU wiring course is free to study with a fee for the certificate exam). A person must open each link before the pitch, and
  set `verified_on` in `backend/data/resources.json`. Whether a course is open for enrolment right now is not known.
  Mobile repair has no mobile-specific course: one Skill India "Mobile Repair Training" link was dropped because it redirected to the
  general course list, and the section uses the Telecom Sector Skill Council's handset technician handbook plus a basic electronics
  course instead. Dairy has no dedicated course (SWAYAM has poultry and animal husbandry courses, so those are used).
- Hindi and Marathi scheme text is machine-translated (Gemini) and labelled as such on screen.

- **Teacher test expert scores.** The five sample descriptions and their expert scores in `backend/data/teacher_tests.json` for the 8
  skill areas were written by the build team so the flow can be shown. A real practitioner must replace each `expert_score` before any
  real teacher is verified. The samples are in English only. The areas are tailoring, shop accounts and GST, digital marketing,
  house wiring, pump and motor repair, mobile repair, photography and video, and computer and CSC services. There is no test for dairy
  and poultry (removed by the team), so no mentor can be matched to that career until one is added. The file is marked `placeholder_scores`.
- **Teacher proof is checked by a model, not a person.** A teacher adds proof (a certificate, an experience letter or a photo of their
  work) and up to 3 photos for each. Plain code first refuses blurry, dark, bright or tiny photos and photos already used (by them or by
  another teacher). A vision model (Gemini, `PROOF_ROUTE`) then describes each photo against a fixed rubric (document type, readable,
  which skill area, an ID number visible, signs of editing, the printed name), and plain code decides, skill by skill: a good certificate or letter for a skill, or two
  good work samples of that same skill, approves that skill (photos for different skills never add up). An approved proof is saved under
  its skill on the Skill check page, shows whether that skill's test is passed, and is locked so the record cannot be swapped. A
  teacher adds a separate proof for each skill they teach; only the new proof is read, and an approved skill is never taken away by it. The model never decides, and text on a photo or typed by the teacher is passed as data, never as an
  instruction. If the model is down or returns invalid output, nothing is approved and the teacher can press Submit for review again.
- **Limits of that check (say so if asked):** a model cannot tell a forged certificate from a real one, so this screens proof; it does not
  authenticate it. A teacher approved this way holds 3 learners instead of 5 until a person confirms them. Every review is stored in
  `proof_reviews`; `python scripts/review_teachers.py audit` lists the latest for a spot-check, and `approve` or `reject` on a teacher
  confirms or overturns it. There is no admin screen. Teacher proof photos go to Gemini (student photos use `VISION_ROUTE` and stay on
  the laptop). Certificates show names and sometimes ID numbers, and on the free tier Google may use submitted data, so check Gemini's
  data terms before a real pilot. The upload page has no consent notice yet.
- Not built in M5: tier 2 (proven by completed journeys and a trust score; needs M6 to M7), mentor notifications (the mentor sees
  requests when they open Requests; the inbox and web push come with M8), embeddings for mentor skills (matching uses the skill ids).
- A declined or lapsed request returns the journey to `path_selected` (the career is already chosen), not `assessed` as the source spec
  says, because the journey already exists at that point.

## Measured so far (small, invented data: describe it as a smoke test, not accuracy)

- Skill extraction on 40 invented sentences: see `scripts/eval_intake.py`. Real speech has not been scored yet.
- Career coverage on the same sentences: 36 of 36 examples with expected skills get a top career built on a matched or closely related skill,
  and all 15 careers appear in some top 3 (`scripts/eval_careers.py`). This does not measure agreement with a human.

## Roadmap (describe only)

IVR line, node hardware, offline packs, live payment rails, partner APIs, SMS and WhatsApp beyond OTP, all 22 languages.
The QR passport is cancelled and is not on the roadmap.
