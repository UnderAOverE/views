Scheduling a maintenance window — with the actual names
Support person submits the booking → POST /v1/maintenance-events on the facade (routers mounted in the host app fdn-c-amp-fapis-py). Body: startTime, endTime, ticketNumber, reason. Headers: X-Client-Id (required), Idempotency-Key (recommended, a UUID), X-Correlation-Id (optional). Handler: schedule_event in routes/zelle/events.py.
Name-tag check → the require_client_id dependency validates X-Client-Id against ZELLE_CLIENT_ALLOWLIST. Missing → 400 VALIDATION_FAILED; not on the list → 403 FORBIDDEN_ACTION.
Sanity checks → EventService.schedule in event_service.py: pydantic window validation (422 on bad input), overlap check against existing rows in the zelle_events collection, and — if an Idempotency-Key was sent — a ledger row in zelle_idempotency (unique on client_id + key; a replay returns the stored response instead of continuing).
Logbook, before anything is sent → an INTENT document into zelle_audit (kind: "INTENT", action: "schedule", attempt_id, actor_client_id, correlation_id) — the pair you saw in Compass.
Sign in to Zelle → TokenBroker in token_broker.py signs an RS256 client assertion (private key at ZELLE_SIGNING_KEY_PATH, key id ZELLE_SIGNING_KID) and POSTs it to the token endpoint — CAT https://auth.zelle.cat.earlywarning.io/token, PROD https://auth.zelle.earlywarning.com/token — with aud = CAT https://auth-zelle.cat.earlywarning.io/oauth2/access/v1/token / PROD https://auth-zelle.earlywarning.com/oauth2/access/v1/token and scope maintenance-event. The access token is cached (~30 min) and reused across calls.
Send the booking → ZomsClient.schedule in zoms_client.py → POST https://api.zelle.cat.earlywarning.io/zoms/v1/events/schedule (PROD: api.zelle.earlywarning.com). Headers: Authorization: Bearer …, request-id (fresh UUID per attempt), idempotency-id (the facade-minted UUID stored on the event). Body: orgId, participantName, submittedName, contactName/Phone/Email auto-filled from ZELLE_ORG_ID / ZELLE_CONTACT_* config, plus the window as scheduledStartDate/scheduledEndDate and ewsHold.
Zelle's answer recorded → the 201 body's maintenanceEventId is stored as ews_event_id on the zelle_events document; an OUTCOME document (same attempt_id) goes into zelle_audit; event status → SCHEDULED. If Zelle accepted but returned no id: status PENDING_UPSTREAM_ID and the caller sees 202 instead of 201.
Receipt to the caller → JSON with eventId (ours — the handle for everything after), status, ticketNumber, the window, and correlationId (also echoed in the X-Correlation-Id response header).
Any failure → one envelope shape: {"error": {"code", "message", "correlationId", "retryable"}} with codes from the fixed list (VALIDATION_FAILED, CONFLICT, FORBIDDEN_ACTION, NOT_FOUND, UPSTREAM_REJECTED, UPSTREAM_UNAVAILABLE, RATE_LIMITED, UPSTREAM_UNCERTAIN), the event lands FAILED (clean rejection) or UNCERTAIN (ambiguous outcome — locked for an operator), and the zelle_audit OUTCOME row records why.


Looking up an event — with the actual names
By id → GET /v1/maintenance-events/{eventId}; the list → GET /v1/maintenance-events?status=SCHEDULED (filter optional). Header: X-Client-Id.
Answered from our own records → EventService.get_event / list_events read the zelle_events collection in the Mongo database fdn-c-amp-fapis-py. No call to Zelle, no token involved — instant.
The status values you can see: PENDING, PENDING_UPSTREAM_ID, SCHEDULED, IN_PROGRESS, COMPLETE, CANCELLED, UNCERTAIN, FAILED.
Live check at the source → GET /v1/maintenance-events/{eventId}/upstream-status → ZomsClient.get_status → GET https://api.zelle.cat.earlywarning.io/zoms/v1/events/{maintenanceEventId} (real call, needs the token from step 5 above). Returns localStatus and upstreamStatus side by side plus checkedAt; 409 if the event has no ews_event_id yet.



The two keys
Think of a wax seal ring. There are two parts to it:

The ring itself (the private key) — only you have it. It's the file on your server, signing.pem. Whoever holds this can press your unique seal.
A photo of what your seal looks like (the public key) — you can hand this to anyone. With the photo, someone can check whether a seal was pressed by your ring. But the photo can't be used to press new seals.
That's the entire trick: one side stamps, the other side only verifies. Nothing secret ever has to travel.

The one-time setup (this is the "registration" EWS still owes us)
Before any of this works, you mail Zelle the photo — the public key. You keep the ring. Zelle files the photo in their records under a short label — the kid ("key id"), which is just a name tag like uat-eamp-key-1 so that later they know which photo to pull out, since a company can have several keys over time.

JWKS is nothing more than the filing cabinet format for those photos. It stands for "JSON Web Key Set" — literally: a small file listing one or more public keys, each with its name tag. When people say "register your JWKS with EWS," they mean: "give us the photo(s) of your seal(s), each labeled, so we can check your stamps later." That's it. There's no magic in it — it's a contact card holding public keys.

What happens on every call, start to finish
Our service writes a short note: "I am client so-and-so, it's 2:03pm, this note expires in two minutes, and it's meant for Zelle's login desk only." (That last part is the aud from earlier — the "To:" line.)
It presses the seal on the note with the private key, and writes the name tag (kid) on the outside — "check this against photo #uat-eamp-key-1."
It sends the sealed note to Zelle's login desk (the token URL).
The login desk reads the name tag, pulls the photo we registered out of their filing cabinet, and compares: does this seal match the photo? Is the note fresh, not expired, addressed to us, from a client we know?
If everything matches, the desk hands back a temporary pass, good for about 30 minutes.
Our service then uses that pass for the actual work — booking, starting, completing maintenance windows — until it expires, at which point it quietly repeats steps 1–5.
The support person triggering all this never sees any of it. They press "schedule"; the seals and passes happen underneath.

Why this design is nice
Nothing secret ever crosses the wire. No password to steal in transit — only sealed notes, and each note dies within minutes and is addressed to one desk only. A stolen note is nearly useless.
Revocation is easy. If the ring is ever compromised, Zelle just removes the photo from their cabinet — every note sealed with that ring stops working instantly.
Rotation is easy. New ring → send a new photo with a new name tag → start stamping with the new one. Old and new can overlap during the change.
Why you're seeing 401 right now
The login desk is reached (network's fine), the note arrives — but when the desk looks for the photo under your name tag, there's nothing in the cabinet yet. Your key (you mentioned the one with CN=uat.eamp.com) hasn't been registered on their side, and the kid you're sending (test_signing_kid) is a placeholder they've never heard of. Until EWS files your public key under an agreed kid — and you put that same kid in ZELLE_SIGNING_KID — every note gets rejected as "seal unknown," no matter how correct everything else is.

That's also why their offer to "decode your client assertion" is useful and safe: you'd be showing them one sealed note (which contains no secret — the ring stays with you), and they can tell you exactly which part of it doesn't match their records.
