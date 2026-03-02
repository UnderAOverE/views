import numpy as np

def mongo_safe(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, dict):
        return {k: mongo_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mongo_safe(v) for v in obj]
    return obj