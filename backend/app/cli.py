"""命令行工具：管理员的创建与升降级。

用法（在 backend 目录下执行）：
    python -m app.cli create-admin --email admin@example.com --password secret123
    python -m app.cli promote --email admin@example.com
    python -m app.cli demote  --email admin@example.com

注意：直接对数据库操作，不受接口层护栏限制，请谨慎使用。
"""

import argparse
import sys

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.core.db import SessionLocal


def _create_admin(email: str, password: str | None) -> int:
    with SessionLocal() as db:
        repo = UserRepository(db)
        user = repo.get_by_email(email)
        if user is None:
            if not password:
                print(f"[错误] 用户 {email} 不存在，创建时需提供 --password", file=sys.stderr)
                return 2
            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_admin=True,
            )
            repo.add(user)
            repo.commit()
            print(f"[完成] 已创建管理员：{email} (id={user.id})")
            return 0
        if password:
            user.hashed_password = hash_password(password)
        user.is_admin = True
        user.is_active = True
        repo.commit()
        print(f"[完成] 已确保 {email} 为管理员 (id={user.id})")
        return 0


def _set_admin(email: str, value: bool) -> int:
    with SessionLocal() as db:
        repo = UserRepository(db)
        user = repo.get_by_email(email)
        if user is None:
            print(f"[错误] 用户 {email} 不存在", file=sys.stderr)
            return 2
        user.is_admin = value
        repo.commit()
        print(f"[完成] {email} 的 is_admin 已设为 {value}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Listing MVP 管理工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-admin", help="创建或提升管理员")
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--password", default=None)

    p_promote = sub.add_parser("promote", help="把已有用户提升为管理员")
    p_promote.add_argument("--email", required=True)

    p_demote = sub.add_parser("demote", help="撤销已有用户的管理员权限")
    p_demote.add_argument("--email", required=True)

    args = parser.parse_args(argv)

    if args.command == "create-admin":
        return _create_admin(args.email, args.password)
    if args.command == "promote":
        return _set_admin(args.email, True)
    if args.command == "demote":
        return _set_admin(args.email, False)
    parser.error("未知命令")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
