"""Read analytics winner packets into a review queue. Never generate or publish."""

import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from strategy.creative_recipes import load_recipe, validate_slug


def import_winners(packet_path: Path, client: str, clients_dir: Path) -> Path:
    validate_slug(client)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if packet.get("schema_version") != 1 or packet.get("kind") != "creative_winners":
        raise ValueError("Unsupported winner packet contract")
    if packet.get("client") != client:
        raise ValueError("Winner packet belongs to another client")
    if packet.get("status") != "needs_review":
        raise ValueError("Analytics packet is blocked; resolve its data status before importing")
    if date.fromisoformat(packet["period_end"]) <= date.fromisoformat(packet["period_start"]):
        raise ValueError("Invalid reporting period")
    candidates = []
    for winner in packet["candidates"]:
        version = str(UUID(winner["version_id"]))
        path = clients_dir / client / "creative-recipes" / version / "recipe.json"
        recipe = load_recipe(path)
        if recipe["client"] != client or recipe["version_id"] != version:
            raise ValueError("Recipe identity does not match winner")
        if recipe["product"] != winner["product"]:
            raise ValueError("Winner product does not match recipe")
        output_role = winner["output_role"]
        outputs = {role for step in recipe["steps"] for role in step["outputs"]}
        if (output_role not in outputs
                or recipe["assets"][output_role]["sha256"] != winner["asset_sha256"]):
            raise ValueError("Winner does not match the recorded output asset")
        candidates.append({**winner, "recipe_path": str(path.resolve()),
                           "limitations": recipe["limitations"],
                           "variation_options": ["model", "setting", "copy", "product"],
                           "selected_changes": {}, "approval": "pending"})
    content = {k: v for k, v in packet.items() if k not in ("generated_at", "packet_id")}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    output = clients_dir / client / "creative-feedback" / f"{digest}.json"
    if output.exists():
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump({"schema_version": 1, "status": "needs_review", "packet_sha256": digest,
                   "source_packet": packet, "candidates": candidates}, stream, indent=2)
    return output
