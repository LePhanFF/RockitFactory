"""
DuckDB schema for the Rockit research database.

Tables:
  backtest_runs    — run-level metadata and aggregate metrics
  trades           — per-trade detail (all Trade dataclass fields)
  session_context  — session-level summary from final deterministic snapshot
  deterministic_tape — 5-min time series (flattened key fields + JSON blob)
  observations     — structured findings linked to trades/runs
  trade_assessments — per-trade AI analysis
  agent_decisions  — per-signal agent pipeline decisions (TAKE/SKIP/REDUCE_SIZE)

Views:
  v_trade_context      — trades JOIN session_context
  v_trade_tape         — trades JOIN deterministic_tape at nearest 5-min
  v_agent_accuracy     — agent decision accuracy by strategy + decision type
  v_agent_vs_mechanical — agent TAKE vs SKIP PnL comparison
"""

import duckdb


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

TABLES = {
    "backtest_runs": """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            run_id          VARCHAR PRIMARY KEY,
            timestamp       TIMESTAMP DEFAULT current_timestamp,
            instrument      VARCHAR NOT NULL,
            sessions        INTEGER,
            total_trades    INTEGER,
            win_rate        DOUBLE,
            profit_factor   DOUBLE,
            net_pnl         DOUBLE,
            max_drawdown    DOUBLE,
            avg_win         DOUBLE,
            avg_loss        DOUBLE,
            expectancy      DOUBLE,
            strategies      JSON,
            config          JSON,
            by_strategy     JSON,
            git_branch      VARCHAR,
            git_commit      VARCHAR,
            notes           VARCHAR,
            report_md       VARCHAR
        )
    """,
    "trades": """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id        VARCHAR,
            run_id          VARCHAR NOT NULL,
            strategy_name   VARCHAR,
            setup_type      VARCHAR,
            day_type        VARCHAR,
            trend_strength  VARCHAR,
            session_date    VARCHAR,
            entry_time      TIMESTAMP,
            exit_time       TIMESTAMP,
            bars_held       INTEGER,
            direction       VARCHAR,
            contracts       INTEGER,
            signal_price    DOUBLE,
            entry_price     DOUBLE,
            exit_price      DOUBLE,
            stop_price      DOUBLE,
            target_price    DOUBLE,
            gross_pnl       DOUBLE,
            commission      DOUBLE,
            slippage_cost   DOUBLE,
            net_pnl         DOUBLE,
            exit_reason     VARCHAR,
            mae_price       DOUBLE,
            mfe_price       DOUBLE,
            mae_bar         INTEGER,
            mfe_bar         INTEGER,
            instrument      VARCHAR,
            metadata        JSON,
            -- computed columns
            risk_points     DOUBLE GENERATED ALWAYS AS (
                CASE WHEN direction = 'LONG'
                     THEN ABS(entry_price - stop_price)
                     ELSE ABS(stop_price - entry_price) END
            ),
            reward_points   DOUBLE GENERATED ALWAYS AS (
                CASE WHEN direction = 'LONG'
                     THEN ABS(target_price - entry_price)
                     ELSE ABS(entry_price - target_price) END
            ),
            outcome         VARCHAR GENERATED ALWAYS AS (
                CASE WHEN net_pnl > 0 THEN 'WIN' ELSE 'LOSS' END
            ),
            PRIMARY KEY (trade_id, run_id)
        )
    """,
    "session_context": """
        CREATE TABLE IF NOT EXISTS session_context (
            session_date        VARCHAR PRIMARY KEY,
            instrument          VARCHAR,
            ib_high             DOUBLE,
            ib_low              DOUBLE,
            ib_range            DOUBLE,
            ib_width_class      VARCHAR,
            day_type            VARCHAR,
            trend_strength      VARCHAR,
            bias                VARCHAR,
            confidence          DOUBLE,
            composite_regime    VARCHAR,
            vix_regime          VARCHAR,
            atr14_daily         DOUBLE,
            prior_day_type      VARCHAR,
            tpo_shape           VARCHAR,
            current_poc         DOUBLE,
            current_vah         DOUBLE,
            current_val         DOUBLE,
            dpoc_migration      VARCHAR,
            cri_status          VARCHAR,
            session_high        DOUBLE,
            session_low         DOUBLE,
            session_close       DOUBLE,
            or_high             DOUBLE,
            or_low              DOUBLE,
            premarket_json      JSON,
            snapshot_json       JSON
        )
    """,
    "deterministic_tape": """
        CREATE TABLE IF NOT EXISTS deterministic_tape (
            session_date        VARCHAR NOT NULL,
            snapshot_time       VARCHAR NOT NULL,
            instrument          VARCHAR DEFAULT 'NQ',
            close               DOUBLE,
            vwap                DOUBLE,
            atr14               DOUBLE,
            adx14               DOUBLE,
            rsi14               DOUBLE,
            ib_high             DOUBLE,
            ib_low              DOUBLE,
            ib_range            DOUBLE,
            ib_width_class      VARCHAR,
            price_vs_ib         VARCHAR,
            extension_multiple  DOUBLE,
            tpo_shape           VARCHAR,
            current_poc         DOUBLE,
            current_vah         DOUBLE,
            current_val         DOUBLE,
            dpoc_migration      VARCHAR,
            day_type            VARCHAR,
            bias                VARCHAR,
            confidence          DOUBLE,
            trend_strength      VARCHAR,
            cri_status          VARCHAR,
            composite_regime    VARCHAR,
            vix_regime          VARCHAR,
            atr14_daily         DOUBLE,
            snapshot_json       JSON,
            PRIMARY KEY (session_date, snapshot_time, instrument)
        )
    """,
    "observations": """
        CREATE TABLE IF NOT EXISTS observations (
            obs_id          VARCHAR PRIMARY KEY,
            created_at      TIMESTAMP DEFAULT current_timestamp,
            scope           VARCHAR,
            strategy        VARCHAR,
            session_date    VARCHAR,
            trade_id        VARCHAR,
            run_id          VARCHAR,
            observation     VARCHAR NOT NULL,
            evidence        VARCHAR,
            source          VARCHAR,
            confidence      DOUBLE
        )
    """,
    "trade_assessments": """
        CREATE TABLE IF NOT EXISTS trade_assessments (
            trade_id                VARCHAR NOT NULL,
            run_id                  VARCHAR NOT NULL,
            assessed_at             TIMESTAMP DEFAULT current_timestamp,
            outcome_quality         VARCHAR,
            why_worked              VARCHAR,
            why_failed              VARCHAR,
            deterministic_support   VARCHAR,
            deterministic_warning   VARCHAR,
            improvement_suggestion  VARCHAR,
            pre_signal_context      JSON,
            PRIMARY KEY (trade_id, run_id)
        )
    """,
    "agent_decisions": """
        CREATE TABLE IF NOT EXISTS agent_decisions (
            decision_id         VARCHAR PRIMARY KEY,
            run_id              VARCHAR,
            trade_id            VARCHAR,
            session_date        VARCHAR,
            signal_time         VARCHAR,
            strategy_name       VARCHAR NOT NULL,
            setup_type          VARCHAR,
            signal_direction    VARCHAR,
            decision            VARCHAR NOT NULL,
            confidence          DOUBLE,
            evidence_direction  VARCHAR,
            bull_score          DOUBLE,
            bear_score          DOUBLE,
            conviction          DOUBLE,
            total_evidence      INTEGER,
            bull_cards          INTEGER,
            bear_cards          INTEGER,
            gate_passed         BOOLEAN,
            gate_cri_status     VARCHAR,
            reasoning           VARCHAR,
            evidence_cards      JSON,
            actual_outcome      VARCHAR,
            actual_pnl          DOUBLE,
            was_correct         BOOLEAN,
            created_at          TIMESTAMP DEFAULT current_timestamp
        )
    """,
}

VIEWS = {
    "v_trade_context": """
        CREATE OR REPLACE VIEW v_trade_context AS
        SELECT
            t.*,
            sc.ib_width_class   AS ctx_ib_width_class,
            sc.day_type         AS ctx_day_type,
            sc.bias             AS ctx_bias,
            sc.confidence       AS ctx_confidence,
            sc.composite_regime AS ctx_composite_regime,
            sc.vix_regime       AS ctx_vix_regime,
            sc.cri_status       AS ctx_cri_status,
            sc.tpo_shape        AS ctx_tpo_shape,
            sc.dpoc_migration   AS ctx_dpoc_migration,
            sc.premarket_json   AS ctx_premarket
        FROM trades t
        LEFT JOIN session_context sc
            ON t.session_date = sc.session_date
    """,
    "v_trade_tape": """
        CREATE OR REPLACE VIEW v_trade_tape AS
        SELECT
            t.*,
            dt.snapshot_time    AS tape_time,
            dt.close            AS tape_close,
            dt.vwap             AS tape_vwap,
            dt.tpo_shape        AS tape_tpo_shape,
            dt.day_type         AS tape_day_type,
            dt.bias             AS tape_bias,
            dt.confidence       AS tape_confidence,
            dt.cri_status       AS tape_cri_status,
            dt.dpoc_migration   AS tape_dpoc_migration,
            dt.composite_regime AS tape_composite_regime
        FROM trades t
        LEFT JOIN deterministic_tape dt
            ON t.session_date = dt.session_date
            AND dt.snapshot_time = (
                SELECT dt2.snapshot_time
                FROM deterministic_tape dt2
                WHERE dt2.session_date = t.session_date
                  AND dt2.snapshot_time <= COALESCE(
                      LPAD(EXTRACT(HOUR FROM t.entry_time)::VARCHAR, 2, '0')
                      || ':' ||
                      LPAD((EXTRACT(MINUTE FROM t.entry_time)::INT / 5 * 5)::VARCHAR, 2, '0'),
                      '10:30'
                  )
                ORDER BY dt2.snapshot_time DESC
                LIMIT 1
            )
    """,
    "v_agent_accuracy": """
        CREATE OR REPLACE VIEW v_agent_accuracy AS
        SELECT
            strategy_name,
            decision,
            COUNT(*) AS total,
            SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) AS correct,
            ROUND(SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
                AS accuracy_pct,
            ROUND(AVG(confidence), 3) AS avg_confidence,
            ROUND(AVG(conviction), 3) AS avg_conviction
        FROM agent_decisions
        WHERE was_correct IS NOT NULL
        GROUP BY strategy_name, decision
    """,
    "v_agent_vs_mechanical": """
        CREATE OR REPLACE VIEW v_agent_vs_mechanical AS
        SELECT
            ad.strategy_name,
            COUNT(*) AS agent_decisions,
            SUM(CASE WHEN ad.decision = 'TAKE' THEN 1 ELSE 0 END) AS takes,
            SUM(CASE WHEN ad.decision = 'SKIP' THEN 1 ELSE 0 END) AS skips,
            SUM(CASE WHEN ad.decision = 'REDUCE_SIZE' THEN 1 ELSE 0 END) AS reduces,
            ROUND(AVG(CASE WHEN ad.decision = 'TAKE' THEN ad.actual_pnl END), 2)
                AS avg_take_pnl,
            ROUND(AVG(CASE WHEN ad.decision = 'SKIP' THEN ad.actual_pnl END), 2)
                AS avg_skip_pnl,
            ROUND(SUM(CASE WHEN ad.decision = 'SKIP' AND ad.actual_pnl < 0
                       THEN 1 ELSE 0 END) * 100.0
                / NULLIF(SUM(CASE WHEN ad.decision = 'SKIP' THEN 1 ELSE 0 END), 0), 1)
                AS skip_would_have_lost_pct
        FROM agent_decisions ad
        WHERE ad.actual_outcome IS NOT NULL
        GROUP BY ad.strategy_name
    """,
}


def create_all_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables and views. Idempotent."""
    for ddl in TABLES.values():
        conn.execute(ddl)
    for ddl in VIEWS.values():
        conn.execute(ddl)


def drop_all_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop all views then tables."""
    for name in VIEWS:
        conn.execute(f"DROP VIEW IF EXISTS {name}")
    for name in TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {name}")
