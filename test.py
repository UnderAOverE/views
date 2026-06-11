Sure — it's just counting how many readings land in one bucket. Let me walk each step.

Remember a bucket = one specific hour of one specific weekday, e.g. Tuesday 2pm. It only ever collects readings from that exact slot. So the question is: over the training window, how many readings pile up in the Tuesday-2pm bucket?

Step 1 — How many Tuesday-2pms are in the window?
Tuesday 2pm happens once a week. The window is 90 days:


90 days / 7 days per week = 12.85  ~= 13 weeks
So in 90 days, "Tuesday 2pm" comes around ~13 times (13 separate Tuesdays).

Step 2 — How many readings land in each Tuesday-2pm hour?
A bucket is one hour wide (2:00-3:00pm). How many samples fall in that hour depends on how often you poll. Polling every 5 minutes:


60 minutes / 5 minutes = 12 readings in that one hour
So each Tuesday 2pm contributes 12 readings.

Step 3 — Multiply: total readings in the bucket


13 Tuesdays  x  12 readings each  ~= 156 readings in the Tuesday-2pm bucket
Step 4 — Compare to the floor
The floor (min_samples_per_bucket) is 30. You have ~156. 156 >> 30, so the bucket clears the floor easily → it gets a band. That's the "Fine."

The general formula:


samples in a bucket  ~=  (weeks in window)  x  (readings per hour from your poll cadence)
                     ~=  (window_days / 7)  x  (60 / poll_minutes)
That's why cadence matters as much as the window. Same 90-day window, but polling slower:


every 30 min ->  13 weeks  x  (60/30 = 2 per hour)  =  ~26 per bucket  ->  UNDER 30, skipped
every 5 min  ->  13 weeks  x  (60/5  = 12 per hour) =  ~156 per bucket ->  way over, fine
So a fast-polled metric (every 5 min) piles up ~156 readings per slot and sails over the 30 floor; a slow-polled one (every 30 min) only gets ~26 and that slot would be skipped as "not enough history to trust." The 156 number is just 13 × 12.
