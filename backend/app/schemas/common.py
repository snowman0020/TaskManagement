from bson import ObjectId


def serialize(doc: dict | None) -> dict | None:
    """Convert Mongo document to a JSON-friendly dict (ObjectId -> str)."""
    if doc is None:
        return None
    out = dict(doc)
    for key, value in out.items():
        if isinstance(value, ObjectId):
            out[key] = str(value)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    return out


def serialize_list(docs: list[dict]) -> list[dict]:
    return [serialize(d) for d in docs]
