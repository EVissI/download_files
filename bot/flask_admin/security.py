"""FAB AUTH_DB: штатный ab_user, плюс админы из web_users."""

from __future__ import annotations

from flask_appbuilder.security.sqla.manager import SecurityManager
from loguru import logger


class WebAdminSecurityManager(SecurityManager):
    def auth_user_db(self, username, password):
        user = super().auth_user_db(username, password)
        if user:
            return user
        return self._auth_web_admin(username, password)

    def _auth_web_admin(self, username, password):
        from bot.common.utils.password import passwords_match
        from bot.db.models import WebUser

        name = (username or "").strip()
        raw = (password or "").strip()
        if not name or not raw:
            return None
        web = self.session.query(WebUser).filter(WebUser.login == name).first()
        if not web or not web.is_admin:
            return None
        if not passwords_match(web.password_hash, web.password_encrypted, raw):
            return None
        user = self.find_user(username=web.login)
        if user is None:
            role = self.find_role(self.auth_role_admin)
            user = self.add_user(
                username=web.login,
                first_name=web.login,
                last_name="Admin",
                email=f"webuser{int(web.id)}@example.com",
                role=role,
                password=raw,
            )
            if user:
                logger.info("Created FAB ab_user from WebUser admin login={}", web.login)
        if user is None or not user.is_active:
            return None
        self.update_user_auth_stat(user, True)
        return user
