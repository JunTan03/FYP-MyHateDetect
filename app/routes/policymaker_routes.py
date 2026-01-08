from flask import Blueprint, render_template, request, flash
import pandas as pd
from app.utils import get_db_connection
import os
from io import BytesIO
import base64
from wordcloud import WordCloud
import plotly.graph_objects as go
from nltk.corpus import stopwords
import re
from collections import Counter
from nltk.corpus import stopwords
import malaya
from datetime import datetime

malay_stopwords = malaya.text.function.get_stopwords()
eng_stop = set(stopwords.words("english"))
custom_stop = {
    "saya", "awak", "kau", "user", "http","https","kita", "kamu", "dia", "mereka", "kami", "yang", "itu", "ini",
    "dan", "atau", "dengan", "dalam", "kepada", "untuk", "akan", "telah", "boleh", "tidak",
    "hanya", "lagi", "kerana", "jika", "oleh", "pada", "sebagai", "adalah", "apa", "semua",
    "daripada", "lebih", "perlu", "juga", "sudah", "masih", "pun", "satu", "mana", "setiap",
    "tiada", "seorang", "bagaimana", "kenapa", "jadi", "mungkin", "mempunyai", "anda",
    "user", "number", "url", "menjadi", "dari", "tetapi", "bahawa", "seperti", "di", "sangat",
    "ada", "apabila", "ia", "ni", "aku", "co", "tco", "tu", "ni", "tak", "dgn", "je", "ke", "yg",
    "dah","la","tapi","kalau","nk","kat","ke", "pon", "pun", "karena", "kerana", "knp"
}
all_stopwords = eng_stop.union(custom_stop).union(malay_stopwords)


policymaker_bp = Blueprint('policymaker', __name__)

@policymaker_bp.route("/visualise/overview", methods=["GET", "POST"])
def overview():
    import pandas as pd
    import re, base64
    from io import BytesIO
    from collections import Counter
    from wordcloud import WordCloud

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets ORDER BY month")
    months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not months:
        flash("No tweet data available. Please upload data first.", "warning")
        return render_template("visualisation/overview.html", months=[], selected_months=[], insights=[], chart_data={}, type_fig="", wordclouds={}, summary_table=[], policy_brief="")

    # Handle month selection and chart type
    if request.method == "POST":
        chart_type = request.form.get("chart_type") or "bar"
        selected_month = request.form.get("month")
        show_all = request.form.get("months") == "1"
        if show_all:
            selected_months = months
        elif selected_month:
            selected_months = [selected_month]
        else:
            selected_months = [months[-1]]
    else:
        selected_months = [months[-1]]
        chart_type = "bar"

    # Query tweets for selected months
    placeholder = ",".join(["%s"] * len(selected_months))
    sql = f"""SELECT month, hate, hate_types, tweet FROM tweets WHERE month IN ({placeholder}) ORDER BY month"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, selected_months)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        flash("No data found for selected filters.", "info")
        return render_template("visualisation/overview.html",
            months=months,
            selected_months=[],
            insights=[],
            chart_data={"months": [], "hate": [], "non_hate": []},
            type_fig="",
            wordclouds={"hate": "", "non_hate": ""},
            summary_table=[],
            policy_brief="No tweet data available."
        )

    df = pd.DataFrame(rows)

    # Tweet counts
    hate_counts = []
    non_hate_counts = []
    for m in selected_months:
        m_df = df[df["month"] == m]
        hate_counts.append(int((m_df["hate"] == "hate").sum()))
        non_hate_counts.append(int((m_df["hate"] == "non-hate").sum()))

    total_hate = sum(hate_counts)
    total_non = sum(non_hate_counts)
    total_all = total_hate + total_non
    hate_pct = round((total_hate / total_all) * 100, 1) if total_all else 0

    # Top hate type
    hate_only_df = df[df["hate"] == "hate"]
    types_flat = []
    for val in hate_only_df["hate_types"].dropna():
        for t in str(val).split(","):
            t_clean = t.strip().lower()
            if t_clean:
                types_flat.append(t_clean)
    type_counter = Counter(types_flat)
    top_type = type_counter.most_common(1)[0][0].capitalize() if type_counter else "None"

    # Peak hate month
    month_hate_map = {m: (df[df["month"] == m]["hate"] == "hate").sum() for m in selected_months}
    peak_month = max(month_hate_map, key=month_hate_map.get) if month_hate_map else "N/A"

    insights = [
        {"label": "Total Tweets", "value": total_all, "icon": "bi bi-chat-dots", "color": "primary"},
        {"label": "Hate %", "value": f"{hate_pct}%", "icon": "bi bi-exclamation-triangle", "color": "danger"},
        {"label": "Top Hate Type", "value": top_type, "icon": "bi bi-flag", "color": "info"},
        {"label": "Peak Hate Month", "value": peak_month, "icon": "bi bi-calendar-event", "color": "secondary"},
    ]

    # Word clouds
    stop_words = eng_stop.union(custom_stop)
    wordclouds = {"non_hate": "", "hate": ""}
    for label, label_key in [("non-hate", "non_hate"), ("hate", "hate")]:
        subset = df[df["hate"] == label]
        if not subset.empty:
            text = " ".join(subset["tweet"].astype(str)).lower()
            tokens = re.findall(r"\b[a-zA-Z]+\b", text)
            filtered = [w for w in tokens if w not in stop_words and not w.startswith("http")]
            clean_text = " ".join(filtered)

            wc = WordCloud(stopwords=stop_words, background_color="white", width=400, height=200).generate(clean_text)
            buffer = BytesIO()
            wc.to_image().save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            wordclouds[label_key] = b64

    # Summary table
    summary_table = [{"type": t.capitalize(), "count": c} for t, c in type_counter.most_common()]

    # Policy brief
    if total_all > 0:
        range_label = "all available data" if "All" in selected_months or len(selected_months) == len(months) else ", ".join(selected_months)
        if top_type != "None":
            policy_brief = f"Between {range_label}, there were {total_hate} hate tweets and {total_non} non-hate tweets. The most frequent hate type was <strong>{top_type}</strong>."
        else:
            policy_brief = f"Between {range_label}, there were {total_hate} hate tweets and {total_non} non-hate tweets. No specific hate type was dominant."
    else:
        policy_brief = "No tweets available for the selected months."

    return render_template("visualisation/overview.html",
        months=months,
        selected_months=selected_months,
        insights=insights,
        chart_data={"months": selected_months, "hate": hate_counts, "non_hate": non_hate_counts},
        wordclouds=wordclouds,
        summary_table=summary_table,
        policy_brief=policy_brief,
        total_tweets=total_all,
        hate_rate=hate_pct,
        non_hate_rate=round((total_non / total_all) * 100, 1) if total_all else 0,
        top_type=top_type,
        month_max_hate=peak_month
    )

def parse_month_str(month_str):
    try:
        return datetime.strptime(month_str, "%B %Y").strftime("%Y-%m")  # From "June 2024" → "2024-06"
    except:
        return None
    
@policymaker_bp.route("/visualise/compare", methods=["GET", "POST"])
def compare():
    import plotly.graph_objects as go
    from collections import Counter
    import pandas as pd
    from datetime import datetime

    def parse_month_str(month_str):
        try:
            return datetime.strptime(month_str, "%B %Y").strftime("%Y-%m")
        except:
            return None

    # Fetch available months
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets ORDER BY month")
    months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not months:
        flash("No tweet data available. Please upload data first.", "warning")
        return render_template("visualisation/compare.html", months=[], show_comparison=False)

    if request.method == "POST":
        month1_raw = request.form.get("month1")
        month2_raw = request.form.get("month2")
        month1_parsed = parse_month_str(month1_raw)
        month2_parsed = parse_month_str(month2_raw)

        if not month1_parsed or not month2_parsed or month1_parsed == month2_parsed:
            flash("Please select two different months to compare.", "warning")
            return render_template("visualisation/compare.html", months=months, show_comparison=False)

        selected = [month1_parsed, month2_parsed]
        placeholder = ",".join(["%s"] * 2)

        # Fetch tweet data
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT month, hate, hate_types
            FROM tweets
            WHERE month IN ({placeholder})
        """, selected)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        df = pd.DataFrame(rows)
        if df.empty:
            flash("No tweet data available for the selected months.", "info")
            return render_template("visualisation/compare.html", months=months, show_comparison=False)

        df["hate"] = df["hate"].replace({1: "hate", 0: "non-hate"})

        # Count hate/non-hate tweets
        counts = {
            m: {
                "hate": ((df["month"] == m) & (df["hate"] == "hate")).sum(),
                "non_hate": ((df["month"] == m) & (df["hate"] == "non-hate")).sum()
            }
            for m in selected
        }

        # Compute hate and non-hate rates
        rates = {}
        for m in selected:
            hate = counts[m]["hate"]
            non_hate = counts[m]["non_hate"]
            total = hate + non_hate
            rates[m] = {
                "hate_rate": round(hate / total * 100, 1) if total else 0,
                "non_hate_rate": round(non_hate / total * 100, 1) if total else 0,
                "total": total
            }

        hate_rate_diff = round(rates[month2_parsed]["hate_rate"] - rates[month1_parsed]["hate_rate"], 1)
        non_hate_rate_diff = round(rates[month2_parsed]["non_hate_rate"] - rates[month1_parsed]["non_hate_rate"], 1)

        # Bar chart: hate vs non-hate
        hate_bar_fig = go.Figure(data=[
            go.Bar(name="Hate", x=[month1_raw, month2_raw], y=[counts[month1_parsed]["hate"], counts[month2_parsed]["hate"]], marker_color="crimson"),
            go.Bar(name="Non-Hate", x=[month1_raw, month2_raw], y=[counts[month1_parsed]["non_hate"], counts[month2_parsed]["non_hate"]], marker_color="green")
        ])
        hate_bar_fig.update_layout(barmode="group", title="Hate vs. Non-Hate Comparison", yaxis_title="Tweet Count")
        hate_bar_chart = hate_bar_fig.to_html(full_html=False)

        # Hate type breakdown
        type_counts = {m: Counter() for m in selected}
        for m in selected:
            m_df = df[(df["month"] == m) & (df["hate"] == "hate") & df["hate_types"].notna()]
            for row in m_df["hate_types"]:
                for t in str(row).split(","):
                    clean = t.strip().lower()
                    if clean:
                        type_counts[m][clean] += 1

        all_types = sorted(set(type_counts[month1_parsed].keys()) | set(type_counts[month2_parsed].keys()))
        type1_vals = [type_counts[month1_parsed].get(t, 0) for t in all_types]
        type2_vals = [type_counts[month2_parsed].get(t, 0) for t in all_types]

        hate_type_fig = go.Figure(data=[
            go.Bar(name=month1_raw, x=all_types, y=type1_vals, marker_color="#1f77b4"),
            go.Bar(name=month2_raw, x=all_types, y=type2_vals, marker_color="#ff7f0e")
        ])
        hate_type_fig.update_layout(barmode="group", title="Hate Type Breakdown Comparison", xaxis_title="Hate Type", yaxis_title="Count")
        hate_type_chart = hate_type_fig.to_html(full_html=False)

        hate_diff = counts[month2_parsed]["hate"] - counts[month1_parsed]["hate"]
        hate_pct = round((hate_diff / max(1, counts[month1_parsed]["hate"])) * 100, 1)

        # Hate type % table
        type1_total = sum(type1_vals)
        type2_total = sum(type2_vals)
        type_pct_table = []
        for t in all_types:
            c1 = type_counts[month1_parsed].get(t, 0)
            c2 = type_counts[month2_parsed].get(t, 0)
            pct1 = round((c1 / type1_total * 100), 1) if type1_total else 0
            pct2 = round((c2 / type2_total * 100), 1) if type2_total else 0
            diff = c2 - c1
            pct_diff = round((diff / c1 * 100), 1) if c1 else None
            type_pct_table.append({
                "type": t.capitalize(),
                "month1_count": c1,
                "month1_pct": pct1,
                "month2_count": c2,
                "month2_pct": pct2,
                "diff": diff,
                "pct_diff": pct_diff
            })

        sorted_table = sorted(type_pct_table, key=lambda x: x["pct_diff"] if x["pct_diff"] is not None else -999, reverse=True)
        top_increase = sorted_table[0]["type"] if sorted_table else "-"

        return render_template("visualisation/compare.html",
            months=months,
            month1=month1_raw,
            month2=month2_raw,
            month1_key=month1_parsed,
            month2_key=month2_parsed,
            hate_bar_chart=hate_bar_chart,
            hate_type_chart=hate_type_chart,
            hate_diff=hate_diff,
            hate_pct=hate_pct,
            show_comparison=True,
            type_pct_table=type_pct_table,
            rates=rates,
            hate_rate_diff=hate_rate_diff,
            non_hate_rate_diff=non_hate_rate_diff,
            top_increase=top_increase
        )

    return render_template("visualisation/compare.html", months=months, show_comparison=False)

@policymaker_bp.route("/visualise/trend", methods=["GET", "POST"])
def trend():
    from statistics import stdev
    from collections import defaultdict

    # ─── 1) Fetch all distinct months ───────────────────────────────
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets ORDER BY month")
    months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not months:
        flash("No tweet data available. Please upload data first.", "warning")
        return render_template("visualisation/trend.html", no_data=True)

    # ─── 2) Selected months ─────────────────────────────────────────
    if request.method == "POST":
        selected_month = request.form.get("month")
        show_all = request.form.get("months") == "1"
        if show_all:
            selected_months = months
        elif selected_month:
            selected_months = [selected_month]
        else:
            selected_months = [months[-1]]
    else:
        selected_months = [months[-1]]

    # ─── 3) Load tweets ─────────────────────────────────────────────
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT month, hate, hate_types FROM tweets ORDER BY month")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows)
    if df.empty:
        return render_template("visualisation/trend.html", no_data=True)

    # ─── 4) Hate vs. Non-Hate Chart ─────────────────────────────────
    pivot = (
        df.groupby(["month", "hate"]).size()
        .reset_index(name="count")
        .pivot(index="month", columns="hate", values="count")
        .fillna(0).astype(int)
        .reindex(months, fill_value=0)
    )
    pivot["non-hate"] = pivot.get("non-hate", 0)
    pivot["hate"] = pivot.get("hate", 0)

    hate_line_fig = go.Figure()
    hate_line_fig.add_trace(go.Scatter(x=months, y=pivot["non-hate"], name="Non-Hate", mode="lines+markers", line=dict(color="green")))
    hate_line_fig.add_trace(go.Scatter(x=months, y=pivot["hate"], name="Hate", mode="lines+markers", line=dict(color="red")))
    hate_line_fig.update_layout(title="Trend: Hate vs. Non-Hate Tweets", xaxis_title="Month", yaxis_title="Count", hovermode="x unified")
    hate_line_html = hate_line_fig.to_html(full_html=False)

    # ─── 5) Hate Type Trends ────────────────────────────────────────
    hate_only = df[df["hate"] == "hate"]
    hate_only = hate_only[hate_only["hate_types"].notna() & (hate_only["hate_types"].str.strip() != "")]
    hate_only["type_list"] = hate_only["hate_types"].str.split(",").map(lambda lst: [t.strip().lower() for t in lst])
    exploded = hate_only.explode("type_list")[["month", "type_list"]]
    type_counts = exploded.groupby(["month", "type_list"]).size().reset_index(name="count")
    type_pivot = type_counts.pivot(index="month", columns="type_list", values="count").fillna(0).astype(int)
    type_pivot = type_pivot.reindex(months, fill_value=0)

    type_trend_fig = go.Figure()
    for col in type_pivot.columns:
        type_trend_fig.add_trace(go.Scatter(x=months, y=type_pivot[col], mode="lines+markers", name=col.capitalize()))
    type_trend_fig.update_layout(title="Trend: Each Hate Type Over Time", xaxis_title="Month", yaxis_title="Count", hovermode="x unified")
    type_trend_html = type_trend_fig.to_html(full_html=False)

    # ─── 6) Summary Insight (Volatility + Spike) ───────────────────────
    volatility = {ht: stdev(type_pivot[ht]) if len(type_pivot[ht]) > 1 else 0 for ht in type_pivot.columns}
    most_volatile = max(volatility.items(), key=lambda x: x[1])[0] if volatility else "-"
    most_stable = min(volatility.items(), key=lambda x: x[1])[0] if volatility else "-"
    peak_month = type_pivot.idxmax().to_dict()
    spike_summary = {ht: peak_month[ht] for ht in type_pivot.columns if type_pivot[ht].max() >= 3}

    trend_summary = {
        "total_hate": int(pivot["hate"].sum()),
        "total_nonhate": int(pivot["non-hate"].sum()),
        "most_volatile": most_volatile.capitalize(),
        "most_stable": most_stable.capitalize(),
        "spike_months": spike_summary,
        "selected_months": selected_months,
    }

    return render_template(
        "visualisation/trend.html",
        months=months,
        hate_line_html=hate_line_html,
        type_trend_html=type_trend_html,
        trend_summary=trend_summary,
        no_data=False
    )

@policymaker_bp.route("/visualise/hate_type", methods=["GET", "POST"])
def hate_type():
    """
    Show a breakdown of total counts per hate-type (e.g., Religion, Gender, Race, etc.)
    for the selected month(s).
    """
    # ─── 1) Pull all distinct months from the 'tweets' table ───────────────────────
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets ORDER BY month")
    months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not months:
        flash("No tweet data available. Please upload data first.", "warning")
        return render_template(
            "visualisation/hate_type.html",
            months=[],
            selected_months=[],
            type_bar_html="",
            summary_table=[]
        )

    # ─── 2) Determine which months are selected ───────────────────────────────────
    if request.method == "POST":
        selected_month = request.form.get("month")
        show_all = request.form.get("months") == "1"
        if show_all:
            selected_months = months
        elif selected_month:
            selected_months = [selected_month]
        else:
            selected_months = [months[-1]]
    else:
        selected_months = [months[-1]]

    # ─── 3) Fetch only hate tweets (hate == 1) for those months ─────────────────
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if "All" in selected_months:
        cursor.execute("""
            SELECT hate_types
            FROM tweets
            WHERE hate = 'hate'
            AND hate_types IS NOT NULL
            ORDER BY month
        """)
    else:
        placeholder = ",".join(["%s"] * len(selected_months))
        sql = f"""
            SELECT hate_types
            FROM tweets
            WHERE month IN ({placeholder})
            AND hate = 'hate'
            AND hate_types IS NOT NULL
            ORDER BY month
        """
        cursor.execute(sql, selected_months)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert to DataFrame (it has a single column: hate_types)
    df = pd.DataFrame(rows)

    # If no hate tweets for those months, render message
    if df.empty:
        flash("No hate‐speech data found for the selected month(s).", "info")
        return render_template(
            "visualisation/hate_type.html",
            months=months,
            selected_months=selected_months,
            type_bar_html="",
            summary_table=[]
        )

    # ─── 4) Explode comma-separated hate_types into individual rows ────────────────
    # Step A: Split each "hate_types" string into a Python list, stripping whitespace, lowercasing
    df["type_list"] = (
        df["hate_types"]
        .str.split(",") 
        .map(lambda lst: [t.strip().lower() for t in lst if t.strip()])
    )

    # Step B: Explode so that each row has exactly one single type in "type_list"
    exploded = df.explode("type_list")[["type_list"]]

    # Step C: Count occurrences of each hate type
    type_counts = (
        exploded
        .groupby("type_list")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # If still empty (shouldn’t be, unless all hate_types were blank), handle gracefully
    if type_counts.empty:
        flash("No valid hate_type labels found after processing.", "warning")
        return render_template(
            "visualisation/hate_type.html",
            months=months,
            selected_months=selected_months,
            type_bar_html="",
            summary_table=[]
        )

    # ─── 5) Build Plotly Bar Chart for hate-type counts with multiple colors ────────
    colors = [
        "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
        "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
        "#008080", "#e6beff", "#9a6324", "#fffac8", "#800000"
    ]
    # Repeat colors if fewer than types
    bar_colors = colors * ((len(type_counts) // len(colors)) + 1)

    bar_fig = go.Figure(
        go.Bar(
            x=type_counts["type_list"].tolist(),
            y=type_counts["count"].tolist(),
            marker_color=bar_colors[:len(type_counts)]
        )
    )
    selected_label = ", ".join(selected_months) if "All" not in selected_months else "All Months"

    bar_fig.update_layout(
        title_text=f"Hate‐Type Distribution ({selected_label})",
        xaxis_title="Hate Type",
        yaxis_title="Count",
        xaxis_tickangle=-45
    )
    type_bar_html = bar_fig.to_html(full_html=False)

    # ─── 6) Build a summary table with % of total ───────────────────────────────────
    total_count = type_counts["count"].sum()
    summary_table = [
        {
            "type": row["type_list"],
            "count": int(row["count"]),
            "percent": round((row["count"] / total_count) * 100, 1)
        }
        for _, row in type_counts.iterrows()
    ]

    # ─── 7) Keyword Extraction Per Hate Type (Based on selected months) ────────────────
    import re
    from collections import defaultdict, Counter

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if "All" in selected_months or selected_months == months:
        cursor.execute("""
            SELECT tweet, hate_types
            FROM tweets
            WHERE hate = 'hate' AND hate_types IS NOT NULL
        """)
    else:
        placeholder = ",".join(["%s"] * len(selected_months))
        sql = f"""
            SELECT tweet, hate_types
            FROM tweets
            WHERE hate = 'hate' AND hate_types IS NOT NULL
            AND month IN ({placeholder})
        """
        cursor.execute(sql, selected_months)

    tweets_data = cursor.fetchall()
    cursor.close()
    conn.close()

    # Group tweets by hate type
    type_tweet_map = defaultdict(list)
    for row in tweets_data:
        if not row["tweet"] or not row["hate_types"]:
            continue
        for t in row["hate_types"].split(","):
            t_clean = t.strip().lower()
            if t_clean:
                type_tweet_map[t_clean].append(row["tweet"])

    # Assuming tweets_data and type_tweet_map already exist
    type_keywords = {}
    stop_words = all_stopwords

    for hate_type, tweets in type_tweet_map.items():
        all_text = " ".join(tweets).lower()
        # Tokenize with regex (alphabetic only)
        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", all_text)  # avoid 1–2 letter junk
        filtered = [t for t in tokens if t not in stop_words]
        most_common = Counter(filtered).most_common(5)  # top 5 keywords
        type_keywords[hate_type] = [word for word, count in most_common]

    # Define cleaner function
    def is_valid_tweet(text):
        text = text.lower()
        return (
            text
            and len(text.split()) >= 4
            and not text.startswith("rt ")
            and "wordle" not in text
            and "http" not in text
        )

    # Apply filtering
    type_examples = {}

    for ttype, tweets in type_tweet_map.items():
        seen = set()
        clean_tweets = []
        for tweet in tweets:
            if tweet in seen:
                continue
            if is_valid_tweet(tweet):
                clean_tweets.append(tweet)
                seen.add(tweet)
            if len(clean_tweets) == 3:
                break
        type_examples[ttype] = clean_tweets

    # ─── 9) Render the template ──────────────────────────────────────────────────
    return render_template(
        "visualisation/hate_type.html",
        months=months,
        selected_months=selected_months,
        type_bar_html=type_bar_html,
        summary_table=summary_table,
        type_keywords=type_keywords,
        type_examples=type_examples
    )

@policymaker_bp.route("/visualise/tweets", methods=["GET", "POST"])
def tweets():
    """
    Display a table of all tweets for selected month(s), 
    showing tweet text, month, hate vs. non-hate, and hate_types.
    """
# 1) Fetch all distinct months to populate the month‐selector
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets ORDER BY month")
    months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not months:
        flash("No tweet data available. Please upload tweets first.", "warning")
        return render_template(
            "visualisation/tweets.html",
            months=[],
            selected_months=[],
            tweet_rows=[],
            summary={},
            hate_types_list=[]
        )

    # 2) Determine which months the user selected (or default to the latest)
    if request.method == "POST":
        selected_month = request.form.get("month")
        show_all = request.form.get("months") == "1"
        if show_all:
            selected_months = months
        elif selected_month:
            selected_months = [selected_month]
        else:
            selected_months = [months[-1]]
    else:
        selected_months = [months[-1]]
        
    # 3) Query all tweets for those months
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if "All" in selected_months:
        cursor.execute("""
            SELECT 
                month,
                tweet,
                hate,
                hate_types
            FROM tweets
            ORDER BY month DESC
        """)
        rows = cursor.fetchall()
    else:
        placeholder = ",".join(["%s"] * len(selected_months))
        sql = f"""
            SELECT 
                month,
                tweet,
                hate,
                hate_types
            FROM tweets
            WHERE month IN ({placeholder})
            ORDER BY month DESC
        """
        cursor.execute(sql, selected_months)
        rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # 4) Post‐process each row:
    #    - Ensure `hate` is exactly "hate" or "non-hate"
    #    - Fill hate_types with empty string if None
    for r in rows:
        if r["hate"] not in ("hate", "non-hate"):
            r["hate"] = "non-hate"
        
        # NEW: only keep hate_types if the row is truly labeled "hate"
        if r["hate"] != "hate":
            # blank it out (so Non‐Hate rows show nothing in that column)
            r["hate_types"] = ""
        else:
            # if it *is* a "hate" row, we leave whatever the DB stored,
            # or convert None→"" just in case:
            r["hate_types"] = r["hate_types"] or ""

    # 5) Compute summary statistics (total tweets, hate vs non-hate counts, top hate type)
    total_tweets = len(rows)
    hate_count   = sum(1 for r in rows if r["hate"] == "hate")
    nonhate_count = total_tweets - hate_count

    # Flatten all hate_types for "hate" rows and count frequency
    all_types = []
    for r in rows:
        if r["hate"] == "hate" and r["hate_types"].strip():
            # split on comma, strip whitespace, lowercase
            for t in r["hate_types"].split(","):
                t_clean = t.strip().lower()
                if t_clean:
                    all_types.append(t_clean)
    type_counter = Counter(all_types)
    if type_counter:
        top_type, top_count = type_counter.most_common(1)[0]
    else:
        top_type, top_count = ("None", 0)

    summary = {
        "total": total_tweets,
        "hate": hate_count,
        "non_hate": nonhate_count,
        "top_type": top_type.capitalize(),
        "top_count": top_count
    }

    # 6) Build a sorted list of all unique hate types (for the Hate Type dropdown)
    unique_types = sorted(set(all_types))

    # 7) Pass everything into the template
    return render_template(
        "visualisation/tweets.html",
        months=months,
        selected_months=selected_months,
        tweet_rows=rows,
        summary=summary,
        hate_types_list=unique_types
    )

