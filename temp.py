
import datetime
import time

# --- 1. Define your initial datetime and pause duration ---

# This is your starting point. In a real application, you might get this
# from a database, a file, or the start of a process.
# For this example, we'll just capture the moment the script begins.
start_time = datetime.datetime.now()

# This is your pause duration in seconds.
pause_seconds = 10

print(f"Start time:          {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Pause duration:      {pause_seconds} seconds")


# --- 2. Calculate the Expiration Time ---

# Use timedelta to represent the pause duration.
# This is the key step: add the duration to the start time.
expiration_time = start_time + datetime.timedelta(seconds=pause_seconds)

print(f"The pause will expire at: {expiration_time.strftime('%Y-%m-%d %H:%M:%S')}")
print("-" * 40)


# --- 3. Compare with the current time ---

def check_if_pause_is_active():
    """Compares the expiration time with the current time."""
    current_time = datetime.datetime.now()

    # The main comparison:
    # If the expiration time is in the future (larger than now), the pause is active.
    if expiration_time > current_time:
        time_remaining = expiration_time - current_time
        print(f"Status Check: The pause is still ACTIVE.")
        # .total_seconds() gives a clean float of the remaining seconds
        print(f"Time remaining: {time_remaining.total_seconds():.2f} seconds.")
        return True
    else:
        print(f"Status Check: The pause has EXPIRED.")
        print("The expiration time is in the past.")
        return False

# --- Let's test it ---

# First check, immediately after starting
print("Performing first check immediately...")
check_if_pause_is_active()
print("\n...waiting for 12 seconds (which is longer than the 10-second pause)...\n")

# Wait for a period longer than the pause
time.sleep(12)

# Second check, after waiting
print("Performing second check after waiting...")
check_if_pause_is_active()
