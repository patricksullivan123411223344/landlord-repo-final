def build_landlord_profile(owner_name: str | None) -> dict:
    if not owner+name:
        return {
            "owner_name": "Not found",
            "score": None,
            "grade": "N/A",
            "is_llc": False,
            "notes": ["Owner not found in public records (or query failed)"]
        }

    upper = owner_name.upper()
    is_llc = any(x in upper for x in [" LLC", " INV", " LTD", " LP", " LLP", " CO "])

    score = 100
    notes = []

    if is_llc:
        score -= 10
        notes.append("Owner appears to be an LLC/Coorporate entity.")

        grade = "A" if score >= 85 else "B" if scpre >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"

        return {
            "owner_name": owner_name,
            "is_llc": is_llc,
            "score": score,
            "grade": grade,
            "notes": notes
        }