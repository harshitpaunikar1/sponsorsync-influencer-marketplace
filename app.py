"""
Flask REST API for SponsorSync influencer marketplace.
Handles briefs, influencer profiles, matching, bids, and chat.
"""
import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from flask import Flask, request, jsonify, g
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from matcher import BrandBrief, InfluencerProfile, InfluencerMatcher
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False


DB_PATH = "sponsorsync.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
    brief_id TEXT PRIMARY KEY,
    brand_name TEXT,
    campaign_title TEXT,
    niches TEXT,
    min_followers INTEGER,
    max_followers INTEGER,
    budget_inr REAL,
    preferred_platforms TEXT,
    status TEXT DEFAULT 'active',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS influencers (
    influencer_id TEXT PRIMARY KEY,
    name TEXT,
    handle TEXT,
    platform TEXT,
    followers INTEGER,
    engagement_rate REAL,
    niches TEXT,
    avg_rate_inr REAL,
    content_quality_score REAL,
    response_rate REAL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS bids (
    bid_id TEXT PRIMARY KEY,
    brief_id TEXT,
    influencer_id TEXT,
    proposed_rate_inr REAL,
    message TEXT,
    status TEXT DEFAULT 'pending',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    bid_id TEXT,
    sender_id TEXT,
    sender_role TEXT,
    content TEXT,
    created_at REAL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
        g.db.commit()
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def row_to_dict(row) -> Dict[str, Any]:
    return dict(row) if row else {}


def create_app() -> "Flask":
    if not FLASK_AVAILABLE:
        raise RuntimeError("Flask required: pip install flask")

    app = Flask(__name__)
    app.teardown_appcontext(close_db)

    # -- Briefs --
    @app.route("/briefs", methods=["GET"])
    def list_briefs():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM briefs WHERE status='active' ORDER BY created_at DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route("/briefs", methods=["POST"])
    def create_brief():
        data = request.get_json(silent=True) or {}
        required = ["brand_name", "campaign_title", "niches", "min_followers",
                     "max_followers", "budget_inr", "preferred_platforms"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        brief_id = f"brief_{int(time.time() * 1000)}"
        db = get_db()
        db.execute(
            "INSERT INTO briefs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (brief_id, data["brand_name"], data["campaign_title"],
             json.dumps(data["niches"]),
             int(data["min_followers"]), int(data["max_followers"]),
             float(data["budget_inr"]),
             json.dumps(data["preferred_platforms"]),
             "active", time.time()),
        )
        db.commit()
        return jsonify({"brief_id": brief_id, "status": "created"}), 201

    # -- Influencers --
    @app.route("/influencers", methods=["GET"])
    def list_influencers():
        db = get_db()
        platform = request.args.get("platform")
        min_followers = request.args.get("min_followers", 0, type=int)
        sql = "SELECT * FROM influencers WHERE followers >= ?"
        params = [min_followers]
        if platform:
            sql += " AND platform=?"
            params.append(platform)
        rows = db.execute(sql, params).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route("/influencers", methods=["POST"])
    def create_influencer():
        data = request.get_json(silent=True) or {}
        required = ["name", "handle", "platform", "followers", "engagement_rate",
                     "niches", "avg_rate_inr"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        inf_id = f"inf_{int(time.time() * 1000)}"
        db = get_db()
        db.execute(
            "INSERT INTO influencers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (inf_id, data["name"], data["handle"], data["platform"],
             int(data["followers"]), float(data["engagement_rate"]),
             json.dumps(data["niches"]),
             float(data["avg_rate_inr"]),
             float(data.get("content_quality_score", 0.7)),
             float(data.get("response_rate", 0.8)),
             time.time()),
        )
        db.commit()
        return jsonify({"influencer_id": inf_id, "status": "created"}), 201

    # -- Matching --
    @app.route("/briefs/<brief_id>/matches", methods=["GET"])
    def match_influencers(brief_id: str):
        if not MATCHER_AVAILABLE:
            return jsonify({"error": "Matcher module unavailable"}), 503
        db = get_db()
        brief_row = db.execute("SELECT * FROM briefs WHERE brief_id=?", (brief_id,)).fetchone()
        if not brief_row:
            return jsonify({"error": "Brief not found"}), 404
        b = row_to_dict(brief_row)
        brief = BrandBrief(
            brief_id=b["brief_id"],
            brand_name=b["brand_name"],
            campaign_title=b["campaign_title"],
            niches=json.loads(b["niches"]),
            target_audience=[],
            min_followers=b["min_followers"],
            max_followers=b["max_followers"],
            min_engagement_rate=0.02,
            budget_inr=b["budget_inr"],
            deliverables=[],
            preferred_platforms=json.loads(b["preferred_platforms"]),
        )
        inf_rows = db.execute("SELECT * FROM influencers").fetchall()
        influencers = []
        for r in inf_rows:
            rd = row_to_dict(r)
            influencers.append(InfluencerProfile(
                influencer_id=rd["influencer_id"],
                name=rd["name"],
                handle=rd["handle"],
                platform=rd["platform"],
                followers=rd["followers"],
                engagement_rate=rd["engagement_rate"],
                niches=json.loads(rd["niches"]),
                audience_demographics={},
                avg_reach=int(rd["followers"] * rd["engagement_rate"]),
                past_brand_categories=[],
                content_quality_score=rd["content_quality_score"],
                response_rate=rd["response_rate"],
                avg_rate_inr=rd["avg_rate_inr"],
            ))

        top_n = request.args.get("top_n", 10, type=int)
        matcher = InfluencerMatcher()
        ranked = matcher.rank(brief, influencers, top_n=top_n)
        return jsonify([
            {"influencer_id": inf.influencer_id, "name": inf.name,
             "score": ms.total_score, "explanation": ms.explanation}
            for ms, inf in ranked
        ])

    # -- Bids --
    @app.route("/bids", methods=["POST"])
    def submit_bid():
        data = request.get_json(silent=True) or {}
        required = ["brief_id", "influencer_id", "proposed_rate_inr"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        bid_id = f"bid_{int(time.time() * 1000)}"
        db = get_db()
        db.execute(
            "INSERT INTO bids VALUES (?,?,?,?,?,?,?)",
            (bid_id, data["brief_id"], data["influencer_id"],
             float(data["proposed_rate_inr"]),
             data.get("message", ""),
             "pending", time.time()),
        )
        db.commit()
        return jsonify({"bid_id": bid_id, "status": "submitted"}), 201

    @app.route("/bids/<bid_id>", methods=["PATCH"])
    def update_bid(bid_id: str):
        data = request.get_json(silent=True) or {}
        new_status = data.get("status")
        if new_status not in ("accepted", "rejected", "withdrawn"):
            return jsonify({"error": "status must be accepted|rejected|withdrawn"}), 400
        db = get_db()
        db.execute("UPDATE bids SET status=? WHERE bid_id=?", (new_status, bid_id))
        db.commit()
        return jsonify({"bid_id": bid_id, "status": new_status})

    # -- Chat --
    @app.route("/bids/<bid_id>/messages", methods=["GET"])
    def get_messages(bid_id: str):
        db = get_db()
        rows = db.execute(
            "SELECT * FROM messages WHERE bid_id=? ORDER BY created_at", (bid_id,)
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route("/bids/<bid_id>/messages", methods=["POST"])
    def send_message(bid_id: str):
        data = request.get_json(silent=True) or {}
        if not data.get("content") or not data.get("sender_id"):
            return jsonify({"error": "sender_id and content required"}), 400
        msg_id = f"msg_{int(time.time() * 1000)}"
        db = get_db()
        db.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?)",
            (msg_id, bid_id, data["sender_id"],
             data.get("sender_role", "influencer"),
             data["content"], time.time()),
        )
        db.commit()
        return jsonify({"message_id": msg_id, "status": "sent"}), 201

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "timestamp": time.time()})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not FLASK_AVAILABLE:
        print("Flask not installed. Run: pip install flask")
    else:
        app = create_app()
        print("Starting SponsorSync API on http://localhost:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
