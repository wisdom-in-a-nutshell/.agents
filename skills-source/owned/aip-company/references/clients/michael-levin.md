## Client sketch: Professor Michael Levin (Thoughtforms Life)

> **Status:** Active
> **Primary deliverable:** YouTube → podcast + site automation
> **Start date:** Dec 2024

---

**Client**

* Name: Professor Michael Levin (Tufts University; Allen Center email domain)
* Primary contacts:

  * [Michael.Levin@tufts.edu](mailto:Michael.Levin@tufts.edu)
  * [michael.levin@allencenter.tufts.edu](mailto:michael.levin@allencenter.tufts.edu)
* Other stakeholders:

  * Arthur Levin (son; involved as collaborator/trainee)
  * Occasional collaborators/guests for “working meetings”
  * Tufts admin/legal reviewers (concerned about ownership, costs, continuity)

**What he does**

* Publishes high-density lectures and talks (bioelectricity, developmental biology, cognition/intelligence, “new biology” themes).
* Uses public content as educational outreach, especially for inspiring young scientists (explicitly not chasing popularity for its own sake).

**Goals**

* Make long-form academic talks easy to consume:

  * Audio-first access (podcast platforms)
  * Readable transcripts
  * Better navigation (chapters, TOC)
  * “Lecture companion” formats that feel like notes/books
* Maintain credibility and correct attribution, especially for any non-Levin speakers.
* Ensure continuity so the feed does not “die” after launch.

**AIP scope (what you do for him)**

* End-to-end “YouTube → podcast + site” infrastructure:

  * Podcast feeds on major platforms (via Transistor)
  * Website on Ghost (thoughtforms-life.aipodcast.ing), with a planned subdomain mapping to podcast.thoughtforms.life (DNS-based)
* Backfill catalog and keep it updated:

  * Initial launch included large backfill (dozens of episodes), backdated to match original release dates.
  * Ongoing automation: when a video in the designated playlist goes public, audio + page updates happen automatically (target was ~30 minutes for feeds/site; later guidance mentions within 24h for “published notifications”).
* Metadata and UX improvements:

  * Show notes adapted from YouTube descriptions
  * Chapters / timestamps
  * Weekly analytics email report (downloads, top episodes, new releases) for monitoring and catching breakage
  * Automated notifications to detect/confirm publishing pipeline health
* Transcripts:

  * High-quality automated transcription with timestamps
  * Post-processing “cleanup” where allowed (remove fillers/false starts, fix punctuation/typos) without changing meaning
  * Transparency disclaimer on transcripts
* Advanced “lecture notes” product:

  * Slide-book format: inline slides paired with aligned transcript segments
  * “Lecture Companion” PDFs with clickable timestamps
  * Dedicated page listing all lecture PDFs (download/search)
  * UX polish: clickable table of contents, link styling in PDFs

**Key preferences and guardrails**

* Ownership and trust:

  * Wants clarity that there is no monetization (no ads/paywalls/sponsorships) and no surprise costs.
  * Wants ability to remove/correct content promptly.
  * Tufts lawyers/admins may ask for explicit statements; open to a simple written agreement.
* Attribution:

  * Comfortable with AIP attribution in site/footer and show notes, and willing to shout out AIP publicly.
  * Prefers clear wording he can reuse for announcements.
* Permissions:

  * Strong preference: downloadable “slides + transcript PDFs” only for his own talks to avoid needing permission from other speakers.
* Attribution correctness:

  * Very sensitive to mislabeling other speakers’ content under his name.
  * If a playlist contains multiple speakers (symposium talks), either remove or correctly attribute per episode.
* Content integrity:

  * Transcript edits must be deletion-focused and never change meaning.
  * Edge cases (animations, no-slide videos, video overlays) can break slide/PDF extraction and must be handled by excluding or improving detection.

**Communication style**

* Appreciative, fast feedback loop, asks clear operational questions.
* Wants simple monitoring and “is the automation broken?” signals.

**Timeline highlights (from email history)**

* Sep 2024: prior connection via Nathan Labenz episode production.
* Dec 27–29, 2024: you reached out after Twitter exchange; clarified pro bono trial, ownership, and continuity.
* Feb–Mar 2025: naming/domain/pilot videos; “ThoughtForms” naming; podcast.thoughtforms.life subdomain plan; RSS expectation.
* Apr 2025: initial site + feeds live; more systematic show notes/chapters; transcript rollout begins.
* May–Jun 2025: workflow discussion (YouTube-first vs upload-to-app); automation to track playlist; big demo and “ready to advertise”; weekly analytics reporting.
* Sep 2025: new playlist content request triggered attribution issues; you removed misattributed items.
* Dec 2025: automation stalled (episodes stuck as drafts), fixed; added automated monitoring emails; major transcript + slide-book + PDF improvements.
* Jan 2026: post-update workflow verified (feeds live, transcript + PDFs generated), ongoing automated “published” notifications.

**Open opportunities**

* AI indexing of his written papers into a topic-based “everything Mike said about X” (collation-only, no rewriting).
* WordPress help for his main site pages.
* Wikipedia page update support.
* Domain mapping finalization (podcast.thoughtforms.life) if Tufts prefers ownership/control.

**Watchouts**

* Any multi-speaker content must be either excluded or carefully credited.
* Slide/PDF generation needs robust “does this video have slides?” detection and animation handling to avoid blank pages or “Transcript unavailable” blocks.
* Keep a clear “who to contact” path so inquiries route to you (not noisy for him).
