10.254.15.1:41498 - "GET /backend/podhealthcheck HTTP/1.1" 200 OK
Exception in callback functools.partial(<function AsyncIOScheduler.wakeup at 0x7faeb3af2f20>, <apscheduler.schedulers.asyncio.AsyncIOScheduler object at 0x7faeb3af2200>) at apscheduler.schedulers.asyncio.AsyncIOScheduler.wakeup()
handle: Handle functools.partial(<function AsyncIOScheduler.wakeup at 0x7faeb3af2f20>, <apscheduler.schedulers.asyncio.AsyncIOScheduler object at 0x7faeb3af2200>)
Traceback (most recent call last):
  File "uvloop/cbhandles.pyx", line 61, in uvloop.loop.Handle._run
  File "/workspace/source/.env/lib64/python3.12/site-packages/apscheduler/schedulers/asyncio.py", line 61, in wakeup
    wait_seconds = self._process_jobs()
                   ^^^^^^^^^^^^^^^^^^^
  File "/workspace/source/.env/lib64/python3.12/site-packages/apscheduler/schedulers/base.py", line 1229, in _process_jobs
    jobstore.update_job(job)
  File "/workspace/source/.env/lib64/python3.12/site-packages/apscheduler/jobstores/mongodb.py", line 116, in update_job
    raise JobLookupError(job.id)
apscheduler.jobstores.base.JobLookupError: 'No job by the id of DigitalResiliency_ibs_outage was found'

log_date":"2025-08-13T23:00:01.078111+00:00","log_level":"INFO","message":"Lock acquired for job: DigitalResiliency_throttle"
025-08-13T23:00:01.376891+00:00","log_level":"WARNING","message":"Skipping Citi Mobile UAT1 un-throttle operation"
log_date":"2025-08-13T23:00:01.376932+00:00","log_level":"INFO","message":"Michelangelo released lock for job: DigitalResiliency_throttle"

INFO: 10.254.15.1:55392 - "GET /backend/podhealthcheck HTTP/1.1" 200 OK
