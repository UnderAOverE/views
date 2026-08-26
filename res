Part 1 - Talking points (15-20 min)
1. The blind spot (2 min) - open with the problem, not the product.

"We monitored business transactions and APIs, but the platform layer underneath them - Gemfire, Cassandra, the databases - had static thresholds only. No learned baseline, no sense of context."
The key line from your slide, said out loud: catch the cause, not the symptom. When a cache cluster degrades, the first visible signal upstream is failed business transactions - by then customers feel it. We wanted to see it at the source, minutes earlier.
One sentence on the old pain: static thresholds either page constantly (set tight) or miss everything (set loose), because "normal" at 2pm Tuesday is not "normal" at 3am Sunday.
2. What it is, in one breath (2 min) - slide 1.

Collect critical platform KPIs through AppDynamics at 1-minute intervals, learn what normal looks like for every metric for every hour of the week, and alert only on sustained, genuine deviations.
Coverage today: 9 Gemfire clusters, 3 Apigee planets (Cassandra + message processors + routers), Oracle and Mongo estates, MQ onboarding next. One framework, same collect-learn-detect model on every platform - onboarding the next platform is repeatable, not a rebuild.
3. How it works - the three-step workflow (4 min) - slide 2.

Collect: a collector polls AppD every minute, writes samples to Mongo. Nothing clever here on purpose - boring and reliable.
Compute: this is the learning step. Two plain-language recipes, and I'd say them exactly like this:
Steady metrics (connection counts, heap, CPU): "find the typical value and the typical wobble, and draw the band a few wobbles wide." (That's median + MAD - median is the middle value, MAD is the typical distance from it. Robust: one bad hour can't drag the baseline.)
Bursty metrics (latency, calls per minute): "keep the middle 99% of everything we've seen, throw away the wildest 1% on each edge, that's the band." (Percentile fit - business-hours peaks don't inflate it.)
Bands are per metric, per hour of week: Monday 9am is compared against history of Monday 9am.
Static hard lines where learning is the wrong tool (disk-fill) - shows judgment, mention it in one sentence.
Alert: compare each minute's sample to its band, then noise controls before any email leaves (that's part 5).
4. Demo 1 (3 min) - Metrics Explorer, the money shot.

Pull up ClientConnectionCount on one Gemfire member: raw line, band overlay, alert dots where breaches happened.
Show the band breathing across the day/week - flat metric, band hugs it; then flip to a bursty metric (average response time) and show the wider percentile band. That one visual contrast explains the two recipes better than any bullet.
5. Why it doesn't spam you (3 min) - this is your differentiator, spend real time here.

"Anyone can detect anomalies. The hard part is not paging people for noise." Then walk the defaults:
15 consecutive violating minutes before an anomaly opens (required_violations) - a blip resets the counter to zero.
The model is allowed to say 'no opinion': fewer than 360 training samples, or a band fitted more than 14 days ago, and it stays silent rather than guessing (min_samples_floor, staleness_window_days).
No alerts on old news: if the triggering sample is older than 5 minutes (pipeline lag), opening is deferred (max_stale_open_seconds).
Symmetric recovery: 15 consecutive normal minutes to resolve, so a flapping metric can't open/close/open all night.
Operator levers: mute during COB drills and planned events; 24h auto-resolve backstop so nothing sticks open forever.
6. Demo 2 (2 min) - a real catch.

Mission Control alerts page: one real anomaly, its lifecycle (opened, how long, resolved), and the email it produced with full context. If you have a story where this caught something before the app teams noticed - tell it here; a single real save lands harder than every architecture slide combined.
7. Wrap: benefits + roadmap (2 min).

Benefits, restated as outcomes: minutes-scale detection at the infrastructure floor, full-stack coverage under AMP, repeatable onboarding.
Next: MQ onboarding, compound alerting (correlated breaches across metrics ranked above single-metric pages), per-datacenter-state bands so DR-drill survivors still get watched.
Close the loop with your opener: "the platform layer is no longer blind."
8. Q&A buffer (2-3 min). Likely questions to have ready: "why 15 minutes, isn't that slow?" (deliberate trade - the config cascades platform -> target -> metric, so a critical metric can override to fewer violations); "why not ML/AI?" (you have the answer from our last conversation: explainability at 3am and low noise were the requirements - median/MAD is defensible to the person being paged, a neural net's reconstruction error is not).

Part 2 - The ClientConnectionCount story, told slowly
Here's the whole life of one high alert, start to end, with your current settings. Imagine the system as a very patient assistant with a notebook.

Step 1 - Writing in the notebook. Every single minute, the collector asks AppDynamics one question: "Right now, how many clients are connected to this Gemfire member?" The answer comes back - say 212 - and it writes it down in Mongo with the time. It never analyzes anything at this step. It just writes. It has been writing every minute for weeks.

Step 2 - Learning what normal is. Separately, a threshold job reads back through weeks of notebook pages and asks: "On Tuesdays around 2pm, what is this number usually?" It lines all those Tuesday-2pm values up and takes the middle one - say 200. That's the median. Then it asks "how far do the values usually stray from 200?" - say about 10. That's the typical wobble (MAD). The band is the middle value plus-or-minus a few wobbles: roughly 160 to 240. That band gets stored as "normal for Tuesday 2pm" for this exact metric on this exact member. Every hour of the week has its own band.

Step 3 - Two humility rules. Before a band is allowed to accuse anything, it must pass two checks from your defaults:

It must have learned from at least 360 real measurements (min_samples_floor). Less than that and it says NO_OPINION - "I haven't seen enough to judge" - and stays silent.
Its lesson must be fresh - fitted within the last 14 days (staleness_window_days). A stale memory of normal is not allowed to page a human.
Step 4 - The quiet minutes. Each new sample gets compared to its hour's band. 2:37pm: 212, inside 160-240, nothing happens. 2:38: 208. 2:39: 215. Silence. This is 99.9% of the system's life.

Step 5 - Something happens. At 2:41pm a client storm starts. The reading is 310 - above 240. Does it send an alert? No. One weird minute is just a blip - maybe a reconnect burst, maybe a collection hiccup. Instead it opens a quiet internal note: PENDING. "I saw something. I'm watching now."

Step 6 - The patience counter. This is required_violations: 15. It needs 15 violating minutes in a row before it will say anything out loud. 2:42: 322, that's 2. 2:43: 315, that's 3... If any single minute dips back inside the band, the counter resets to zero and the suspicion is dropped - it really was noise. But the storm holds: 305, 318, 330... at 2:55pm the 15th consecutive breach lands.

Step 7 - One last sanity check. Before flipping to OPEN, it checks the triggering sample's age (max_stale_open_seconds: 300): is this reading less than 5 minutes old? If the pipeline had been lagging and this is old news, it holds off - nobody gets woken up for something that may already be over. Here the sample is fresh, so:

Step 8 - The alert. The anomaly flips PENDING -> OPEN, and now - for the first time, 15 minutes after the storm began - an email goes out: which metric, which member, current value (330), the band it broke (160-240), and how long it's been breaching. It also appears on the Mission Control dashboard. (Unless an operator has muted notifications - say, during a COB drill - in which case it's recorded but nobody is paged.)

Step 9 - Recovery, with the same patience. Someone fixes the client storm. Readings drop: 238, 225, 210... The system now wants 15 consecutive normal minutes (resolve_after_count: 15) before it flips OPEN -> RESOLVED and sends the all-clear email. Same reason as before, mirrored: a metric bouncing on the band edge must not spam open-closed-open. One extra kindness here: the close path skips the min-samples guard - an open anomaly is always allowed to close, even if the band has since lost its opinion.

Step 10 - The backstops. If an anomaly somehow stays open 24 hours without closing normally - say the band went NO_OPINION so the close path never got its 15 clean comparisons - stale_resolve_hours: 24 auto-resolves it rather than leaving it stuck forever. Resolved records live for 90 days (anomalies_retention_days) for review, then expire on their own.

The one-sentence summary you can end the demo with: "With these settings, a sustained connection spike pages a human about 15 to 16 minutes after it starts - and that 15 minutes of patience is exactly what buys us near-zero false pages." If someone asks "can critical metrics be faster?", the answer is yes - the config cascades from platform defaults down to per-metric overrides, so that trade is tunable per metric.
