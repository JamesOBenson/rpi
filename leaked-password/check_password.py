#!/usr/bin/env python3
"""
Leaked Password Checker
=======================
100% offline password security analysis.
"""

import sys
import hashlib
import re
import string
import math
from typing import Optional

try:
    from hibp_db import local_breach_count
except ImportError:  # hibp_db.py missing — online check only
    def local_breach_count(password):
        return None


COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "passw0rd", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123", "welcome",
    "jesus", "ninja", "mustang", "password1234", "admin", "starwars", "hello",
    "charlie", "donald", "access", "123456789", "1234", "12345", "1234567890",
    "password12345", "qwerty123", "admin123", "root", "toor", "pass", "test",
    "guest", "master123", "changeme", "welcome1", "welcome123", "iloveyou1",
    "batman", "batman1", "trustno123", "loveme", "hunter2", "hottie", "sexy",
    "love", "pepper", "hunter", "soccer", "monkey1", "monkey123", "batman123"
}


def calculate_entropy(password: str) -> float:
    """Calculate password entropy in bits."""
    pool_size = 0
    if any(c.islower() for c in password):
        pool_size += 26
    if any(c.isupper() for c in password):
        pool_size += 26
    if any(c.isdigit() for c in password):
        pool_size += 10
    if any(c in string.punctuation for c in password):
        pool_size += 32
    
    if pool_size == 0:
        pool_size = 26
    
    return len(password) * math.log2(pool_size)


def estimate_crack_time(entropy: float, guesses_per_second: float = 10_000_000_000) -> str:
    """Estimate time to crack at 10B guesses/second."""
    seconds = 2 ** entropy / guesses_per_second
    
    if seconds < 1:
        return "instant"
    elif seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        return f"{seconds/60:.1f} minutes"
    elif seconds < 86400:
        return f"{seconds/3600:.1f} hours"
    elif seconds < 31536000:
        return f"{seconds/86400:.1f} days"
    elif seconds < 31536000 * 100:
        return f"{seconds/31536000:.1f} years"
    else:
        return f"{seconds/31536000:.0f} years"


def check_patterns(password: str) -> list:
    """Detect common weak patterns."""
    issues = []
    pwd_lower = password.lower()
    
    weak_words = ["password", "pass", "word", "admin", "user", "login", "letmein",
                  "welcome", "monkey", "dragon", "master", "sunshine", "princess"]
    for word in weak_words:
        if word in pwd_lower:
            issues.append(f"Contains weak word: '{word}'")
    
    patterns = ["qwerty", "asdf", "zxcv", "1234", "4321", "abcd", "qazwsx"]
    for pat in patterns:
        if pat in pwd_lower:
            issues.append(f"Keyboard pattern: '{pat}'")
    
    if re.search(r'(.)\1{2,}', password):
        issues.append("Repeated characters (3+)")
    
    if password.islower() and password.isalpha():
        issues.append("All lowercase letters")
    elif password.isupper() and password.isalpha():
        issues.append("All uppercase letters")
    
    if len(password) < 8:
        issues.append("Less than 8 characters")
    
    return issues


def check_common_password(password: str) -> bool:
    """Check against common passwords list."""
    return password.lower() in COMMON_PASSWORDS


def check_hibp_online(password: str) -> dict:
    """Check HIBP Pwned Passwords API (k-anonymity)."""
    try:
        import urllib.request
        
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]
        
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read().decode()
        
        for line in data.splitlines():
            parts = line.split(':')
            if parts[0] == suffix:
                return {"pwned": True, "count": int(parts[1])}
        
        return {"pwned": False, "count": 0}
    except Exception as e:
        return {"error": str(e)}


def get_strength_rating(entropy: float, is_common: bool, patterns: list) -> str:
    """Determine overall strength rating."""
    if is_common or len(patterns) >= 3 or entropy < 40:
        return "weak"
    if len(patterns) >= 1 or entropy < 60:
        return "moderate"
    if entropy < 80:
        return "good"
    return "strong"


def analyze_password(password: str, check_online: bool = False) -> dict:
    """Full password analysis."""
    entropy = calculate_entropy(password)
    is_common = check_common_password(password)
    patterns = check_patterns(password)
    strength = get_strength_rating(entropy, is_common, patterns)
    
    report = {
        "password": "*" * len(password),
        "length": len(password),
        "entropy": round(entropy, 1),
        "crack_time": estimate_crack_time(entropy),
        "is_common": is_common,
        "patterns": patterns,
        "strength": strength,
        "hibp": None
    }
    
    if check_online:
        count = local_breach_count(password)
        if count is not None:
            report["hibp"] = {"pwned": count > 0, "count": count, "source": "local"}
        else:
            report["hibp"] = check_hibp_online(password)
    
    return report


def print_report(report: dict):
    """Print formatted report."""
    print("=" * 50)
    print("  PASSWORD SECURITY ANALYSIS")
    print("=" * 50)
    print()
    print(f"Length:           {report['length']} characters")
    print(f"Entropy:          {report['entropy']} bits")
    print(f"Estimated crack:  {report['crack_time']}")
    print()
    
    if report['is_common']:
        print("⚠ COMMON PASSWORD DETECTED")
    if report['patterns']:
        print("⚠ PATTERNS FOUND:")
        for p in report['patterns']:
            print(f"  • {p}")
    
    if report['hibp']:
        print()
        if report['hibp'].get('pwned'):
            src = " (local database)" if report['hibp'].get('source') == 'local' else ""
            print(f"⚠ BREACHED: Found in {report['hibp']['count']:,} data breaches{src}")
        elif 'error' not in report['hibp']:
            src = " (local database)" if report['hibp'].get('source') == 'local' else ""
            print(f"✓ Not found in HIBP database{src}")
        else:
            print(f"⚠ Could not check HIBP: {report['hibp']['error']}")
    
    print()
    print("=" * 50)
    strength_colors = {
        "weak": "🔴 WEAK",
        "moderate": "🟡 MODERATE",
        "good": "🟢 GOOD",
        "strong": "🟢 STRONG"
    }
    print(f"  STRENGTH: {strength_colors.get(report['strength'], report['strength'].upper())}")
    print("=" * 50)
    
    if report['strength'] in ["weak", "moderate"]:
        print("\nRecommendations:")
        if report['length'] < 12:
            print("  • Use at least 12 characters")
        if report['is_common']:
            print("  • Avoid common passwords")
        if report['patterns']:
            print("  • Remove predictable patterns")
        print("  • Use a passphrase (4+ random words)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_password.py <password>")
        print("       python3 check_password.py --check <password>  (online HIBP check)")
        sys.exit(1)
    
    check_online = "--check" in sys.argv
    # Get password (skip --check flag if present)
    password = sys.argv[1] if not check_online else sys.argv[2]
    
    if not password:
        print("Error: Password cannot be empty")
        sys.exit(1)
    
    report = analyze_password(password, check_online=check_online)
    print_report(report)


if __name__ == "__main__":
    main()