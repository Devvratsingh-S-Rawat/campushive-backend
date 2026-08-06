"""Safe diagnostic — shows enough to spot the bug, never the full secret."""
from app.config import settings


def mask(s):
    s = str(s)
    if len(s) <= 8:
        return "*" * len(s)
    return s[:4] + "*" * (len(s) - 8) + s[-4:]


kid = settings.razorpay_key_id
ksec = settings.razorpay_key_secret

print("KEY ID")
print("  masked:      ", mask(kid))
print("  length:      ", len(kid))
print("  starts 'rzp_test_':", kid.startswith("rzp_test_"))
print("  clean (no stray whitespace):", kid == kid.strip())
print("  clean (no quote chars):     ", '"' not in kid and "'" not in kid)
print()
print("KEY SECRET")
print("  masked:      ", mask(ksec))
print("  length:      ", len(ksec))
print("  clean (no stray whitespace):", ksec == ksec.strip())
print("  clean (no quote chars):     ", '"' not in ksec and "'" not in ksec)
print()
print("id and secret are different values (not swapped/duplicated):", kid != ksec)
