import json
import logging
from datetime import datetime, date
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import globalvars
from utilities.database.base_dbdriver import (
    AdminAudit,
    ContentLoad,
    CserEvents,
    GameplayUsers,
    ScheduledRestarts,
    S3SurveyData,
    SurveyRaw,
    SurveyTotals,
    UserAchievements,
    UserStats,
)
from utilities.database import base_dbdriver, dbengine

log = logging.getLogger('STATSDB')


def _json_default(obj):
    """Serialize custom objects for JSON by returning their ``__dict__``."""
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


class base_stats_dbdriver:
    def __init__(self, config):
        # wait until MariaDB is initialized elsewhere
        while globalvars.mariadb_initialized != True:
            continue

        # set up the engine & session
        self.db_driver = dbengine.create_database_driver()
        self.db_driver.connect()
        self.session = self.db_driver.get_session()

        # assign ORM classes
        self.CserEvents        = CserEvents
        self.S3SurveyData      = S3SurveyData
        self.SurveyRaw         = SurveyRaw
        self.SurveyTotals      = SurveyTotals
        self.GameplayUsers     = GameplayUsers
        self.UserAchievements  = UserAchievements
        self.UserStats         = UserStats
        self.ContentLoad       = ContentLoad
        self.AdminAudit        = AdminAudit
        self.ScheduledRestarts = ScheduledRestarts

    def log_event(self, event_type, data):
        # insert raw CSER event data as JSON
        try:
            ev = self.CserEvents(
                event_type=event_type,
                event_time=datetime.utcnow(),
                data=json.dumps(data, default=_json_default),
            )
            self.session.add(ev)
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to log event: {e}")
            self.session.rollback()
            return False

    def record_s3surveydata(self, results):
        # store steam3 survey data
        try:
            filtered = {k: v for k, v in results.items() if hasattr(self.S3SurveyData, k)}
            raw = self.S3SurveyData(**filtered)
            self.session.add(raw)
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to record steam3 survey data: {e}")
            self.session.rollback()
            return False

    def record_survey(self, results):
        # store survey results and update aggregated totals
        try:
            raw = self.SurveyRaw(
                ts=datetime.utcnow(),
                data=json.dumps(results, default=_json_default),
            )
            self.session.add(raw)

            for field, value in results.items():
                if field == 'DecryptionOK':
                    continue
                val = str(value)
                tot = (
                    self.session
                        .query(self.SurveyTotals)
                        .filter_by(field=field, option_value=val)
                        .first()
                )
                if tot:
                    tot.count += 1
                else:
                    tot = self.SurveyTotals(field=field, option_value=val, count=1)
                    self.session.add(tot)

            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to record survey: {e}")
            self.session.rollback()
            return False

    def record_gameplay(self, game, user_id, day=None):
        # insert unique gameplay user entry (duplicates ignored)
        day = day or date.today()
        gu = self.GameplayUsers(day=day, game=game, user_id=user_id)
        self.session.add(gu)
        try:
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
            return False

    def get_user_achievement_status(self, user_id, app_id, achievement):
        # return True if the user has unlocked the achievement
        row = (
            self.session
                .query(self.UserAchievements.unlocked)
                .filter_by(
                    user_id=user_id,
                    app_id=app_id,
                    ach_name=achievement
                )
                .first()
        )
        return bool(row and row[0])

    def get_user_stats(self, user_id, app_id):
        # return a mapping of stat name to value for the user
        rows = (
            self.session
                .query(self.UserStats.stat, self.UserStats.value)
                .filter_by(user_id=user_id, app_id=app_id)
                .all()
        )
        return {stat: val for stat, val in rows}

    def record_content_load(self, server, event, day=None):
        # record content load starts or finishes
        day = day or date.today()
        rec = (
            self.session
                .query(self.ContentLoad)
                .filter_by(day=day, server=server)
                .first()
        )
        if not rec:
            rec = self.ContentLoad(day=day, server=server, starts=0, finishes=0)
            self.session.add(rec)

        if event == 'start':
            rec.starts += 1
        else:
            rec.finishes += 1

        self.session.commit()

    def get_gameplay(self, day):
        # return distinct user counts per game for a given day
        rows = (
            self.session
                .query(
                    self.GameplayUsers.game,
                    func.count(func.distinct(self.GameplayUsers.user_id))
                )
                .filter_by(day=day)
                .group_by(self.GameplayUsers.game)
                .all()
        )
        return {game: count for game, count in rows}

    def get_content(self, day):
        # return starts/finishes per server for a given day
        rows = (
            self.session
                .query(
                    self.ContentLoad.server,
                    self.ContentLoad.starts,
                    self.ContentLoad.finishes
                )
                .filter_by(day=day)
                .all()
        )
        return {srv: {'starts': s, 'finishes': f} for srv, s, f in rows}

    def get_survey_totals(self):
        # return aggregated survey totals
        rows = (
            self.session
                .query(
                    self.SurveyTotals.field,
                    self.SurveyTotals.option_value,
                    self.SurveyTotals.count
                )
                .all()
        )
        totals = {}
        for field, opt, cnt in rows:
            totals.setdefault(field, {})[opt] = cnt
        return totals

    def record_audit(self, admin, action, payload):
        # log an admin action for accountability
        try:
            au = self.AdminAudit(
                admin=admin,
                action=action,
                payload=json.dumps(payload, default=_json_default),
                ts=datetime.utcnow(),
            )
            self.session.add(au)
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to record audit: {e}")
            self.session.rollback()
            return False

    def schedule_restart(self, server_id, ts):
        # schedule a server restart
        try:
            sr = self.ScheduledRestarts(server_id=server_id, restart_time=ts)
            self.session.add(sr)
            self.session.commit()
            return True
        except Exception as e:
            log.error(f"Failed to schedule restart: {e}")
            self.session.rollback()
            return False

    def get_scheduled_restarts(self):
        # retrieve all scheduled restarts
        rows = self.session.query(self.ScheduledRestarts).all()
        return [
            {'id': r.id, 'server_id': r.server_id, 'time': str(r.restart_time)}
            for r in rows
        ]

    def cancel_scheduled_restart(self, rid):
        # cancel a previously scheduled restart
        try:
            deleted = (
                self.session
                    .query(self.ScheduledRestarts)
                    .filter_by(id=rid)
                    .delete()
            )
            self.session.commit()
            return deleted > 0
        except Exception as e:
            log.error(f"Failed to cancel scheduled restart: {e}")
            self.session.rollback()
            return False


# lazily instantiate a module-level driver and expose its methods
_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = base_stats_dbdriver(None)
    return _driver


def __getattr__(name):
    """Delegate attribute access to the underlying driver instance."""
    return getattr(_get_driver(), name)

